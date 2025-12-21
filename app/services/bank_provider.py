"""Bank provider client interface and implementations."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings


class BankProviderClient(ABC):
    """Abstract interface for Open Banking providers."""
    
    @abstractmethod
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """List available institutions for a country."""
        pass
    
    @abstractmethod
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new requisition/consent."""
        pass
    
    @abstractmethod
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Get requisition details."""
        pass
    
    @abstractmethod
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """List accounts associated with a requisition."""
        pass
    
    @abstractmethod
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Get account details."""
        pass
    
    @abstractmethod
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Get account balances."""
        pass
    
    @abstractmethod
    async def get_transactions(
        self, 
        account_id: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get account transactions."""
        pass


class MockBankProvider(BankProviderClient):
    """Mock implementation for testing."""
    
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """Return mock institutions."""
        return [
            {
                "id": "MOCK_BANK_CZ",
                "name": "Mock Bank CZ",
                "country": country,
                "logo": "https://example.com/logo.png"
            }
        ]
    
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return mock requisition."""
        return {
            "id": f"req_mock_{datetime.utcnow().timestamp()}",
            "status": "created",
            "institution_id": institution_id,
            "redirect": "https://mock-bank.example.com/auth",
            "reference": reference or "",
            "created": datetime.utcnow().isoformat(),
        }
    
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Return mock requisition details."""
        return {
            "id": requisition_id,
            "status": "linked",
            "accounts": [f"acc_mock_{i}" for i in range(2)],
        }
    
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """Return mock account IDs."""
        return [f"acc_mock_{i}" for i in range(2)]
    
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Return mock account details."""
        return {
            "id": account_id,
            "iban": "CZ6508000000192000145399",
            "currency": "CZK",
            "name": "Mock Checking Account",
            "ownerName": "John Doe",
        }
    
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Return mock balances."""
        return {
            "balances": [
                {
                    "balanceAmount": {"amount": "1000.50", "currency": "CZK"},
                    "balanceType": "expected",
                    "referenceDate": datetime.utcnow().date().isoformat(),
                }
            ]
        }
    
    async def get_transactions(
        self, 
        account_id: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Return mock transactions."""
        return {
            "transactions": {
                "booked": [
                    {
                        "transactionId": f"tx_{i}",
                        "bookingDate": (datetime.utcnow() - timedelta(days=i)).date().isoformat(),
                        "valueDate": (datetime.utcnow() - timedelta(days=i)).date().isoformat(),
                        "transactionAmount": {"amount": f"{(-1)**(i) * (i+1) * 100}", "currency": "CZK"},
                        "creditorName": f"Merchant {i}" if i % 2 == 0 else None,
                        "debtorName": f"Merchant {i}" if i % 2 == 1 else None,
                        "remittanceInformationUnstructured": f"Payment {i}",
                    }
                    for i in range(10)
                ],
                "pending": []
            }
        }


class TrueLayerProvider(BankProviderClient):
    """TrueLayer implementation for Open Banking."""
    
    def __init__(self):
        self.base_url = settings.TRUELAYER_BASE_URL
        self.client_id = settings.TRUELAYER_CLIENT_ID
        self.client_secret = settings.TRUELAYER_CLIENT_SECRET
        self._token = None
        self._token_expires_at = None
    
    async def _get_token(self) -> str:
        """Return currently set user access token.
        
        TrueLayer's data endpoints require a user access token obtained via the
        authorization code flow. We do not use client credentials here.
        """
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._token
        if self._token:
            # No expiry known; return as-is
            return self._token
        raise RuntimeError("TrueLayer user access token not set")
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request."""
        token = await self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

    def set_user_token(self, token: str, expires_in: Optional[int] = None) -> None:
        """Set the user access token to be used for API requests."""
        self._token = token
        if expires_in:
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))
        else:
            self._token_expires_at = None

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for user access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.TRUELAYER_AUTH_URL}/connect/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            resp.raise_for_status()
            return resp.json()
    
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """List institutions for a country.
        
        Note: TrueLayer's providers endpoint is hosted on the AUTH domain
        and returns a JSON array, not an object with "results".
        It does not require an access token; we pass clientId to filter
        providers enabled for this application.
        """
        params = {"clientId": self.client_id}
        providers: List[Dict[str, Any]] = []
        async with httpx.AsyncClient() as client:
            # First, try with country filter (if provided)
            if country:
                try:
                    resp = await client.get(f"{settings.TRUELAYER_AUTH_URL}/api/providers", params={**params, "country": country})
                    resp.raise_for_status()
                    providers = resp.json() or []
                except httpx.HTTPError:
                    providers = []
            # Fallback: fetch all configured providers for this client
            if not providers:
                resp_all = await client.get(f"{settings.TRUELAYER_AUTH_URL}/api/providers", params=params)
                resp_all.raise_for_status()
                providers = resp_all.json() or []

        # Map to common format
        mapped = [
            {
                "id": p.get("provider_id", ""),
                "name": p.get("display_name", ""),
                "country": p.get("country_code", ""),
                "logo": p.get("logo_uri", "")
            }
            for p in providers
        ]
        # If we have results and a country was specified but TL returned mixed countries,
        # filter to requested country; otherwise return all (fallback case).
        if country and any(item.get("country") == country for item in mapped):
            return [item for item in mapped if item.get("country") == country]
        return mapped
    
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a connection/authorization for TrueLayer.
        
        Note: TrueLayer uses an auth flow, not requisitions.
        This returns an auth URL that the user needs to visit.
        """
        # Build auth link
        from urllib.parse import urlencode
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": "info accounts balance transactions",
            "redirect_uri": redirect_url,
            "providers": institution_id,
        }
        if reference:
            params["state"] = reference
        
        auth_url = f"{settings.TRUELAYER_AUTH_URL}/?{urlencode(params)}"
        
        return {
            "id": f"tl_{reference or institution_id}",
            "status": "created",
            "institution_id": institution_id,
            "redirect": auth_url,
            "reference": reference or "",
            "created": datetime.utcnow().isoformat(),
        }
    
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Get connection status.
        
        For TrueLayer, this is handled differently - we check if we have accounts.
        """
        return {
            "id": requisition_id,
            "status": "linked",
            "accounts": [],  # Will be populated after OAuth flow
        }
    
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """List accounts for user."""
        data = await self._request("GET", "/api/accounts")
        accounts = data.get("results", [])
        return [acc["account_id"] for acc in accounts]
    
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Get account details."""
        data = await self._request("GET", f"/api/accounts/{account_id}")
        account = data.get("results", [{}])[0]
        return {
            "id": account_id,
            "iban": account.get("account_number", {}).get("iban", ""),
            "currency": account.get("currency", ""),
            "name": account.get("display_name", f"Account {account_id[:8]}"),
            "ownerName": account.get("account_holder_name", ""),
            "account_type": account.get("account_type", ""),
        }
    
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Get account balances."""
        data = await self._request("GET", f"/api/accounts/{account_id}/balance")
        balances_data = data.get("results", [])
        
        # Convert TrueLayer format to our standard format
        balances = []
        for bal in balances_data:
            balances.append({
                "balanceAmount": {
                    "amount": str(bal.get("current", 0)),
                    "currency": bal.get("currency", "")
                },
                "balanceType": "expected",
                "referenceDate": bal.get("update_timestamp", datetime.utcnow().isoformat())[:10],
            })
        
        return {"balances": balances}
    
    async def get_transactions(
        self, 
        account_id: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get account transactions."""
        params = {}
        if date_from:
            params["from"] = date_from.date().isoformat()
        if date_to:
            params["to"] = date_to.date().isoformat()
        
        data = await self._request(
            "GET", 
            f"/api/accounts/{account_id}/transactions",
            params=params
        )
        
        transactions_data = data.get("results", [])
        
        # Convert TrueLayer format to our standard format
        booked = []
        for tx in transactions_data:
            booked.append({
                "transactionId": tx.get("transaction_id", ""),
                "bookingDate": tx.get("timestamp", "")[:10],
                "valueDate": tx.get("timestamp", "")[:10],
                "transactionAmount": {
                    "amount": str(tx.get("amount", 0)),
                    "currency": tx.get("currency", "")
                },
                "creditorName": tx.get("merchant_name") if tx.get("transaction_type") == "DEBIT" else None,
                "debtorName": tx.get("merchant_name") if tx.get("transaction_type") == "CREDIT" else None,
                "remittanceInformationUnstructured": tx.get("description", ""),
            })
        
        return {
            "transactions": {
                "booked": booked,
                "pending": []
            }
        }


class GoCardlessProvider(BankProviderClient):
    """GoCardless (formerly Nordigen) implementation."""
    
    def __init__(self):
        self.base_url = settings.GOCARDLESS_BASE_URL
        self.secret_id = settings.GOCARDLESS_SECRET_ID
        self.secret_key = settings.GOCARDLESS_SECRET_KEY
        self._token = None
        self._token_expires_at = None
    
    async def _get_token(self) -> str:
        """Get or refresh access token."""
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/token/new/",
                json={
                    "secret_id": self.secret_id,
                    "secret_key": self.secret_key,
                }
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access"]
            # Token typically expires in 24 hours
            self._token_expires_at = datetime.utcnow() + timedelta(hours=23)
            return self._token
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request."""
        token = await self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """List institutions for a country."""
        data = await self._request("GET", f"/institutions/?country={country}")
        return data
    
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a requisition."""
        payload = {
            "institution_id": institution_id,
            "redirect": redirect_url,
        }
        if reference:
            payload["reference"] = reference
        
        return await self._request("POST", "/requisitions/", json=payload)
    
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Get requisition details."""
        return await self._request("GET", f"/requisitions/{requisition_id}/")
    
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """List accounts from requisition."""
        data = await self.get_requisition(requisition_id)
        return data.get("accounts", [])
    
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Get account details."""
        return await self._request("GET", f"/accounts/{account_id}/details/")
    
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Get account balances."""
        return await self._request("GET", f"/accounts/{account_id}/balances/")
    
    async def get_transactions(
        self, 
        account_id: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get account transactions."""
        params = {}
        if date_from:
            params["date_from"] = date_from.date().isoformat()
        if date_to:
            params["date_to"] = date_to.date().isoformat()
        
        return await self._request(
            "GET", 
            f"/accounts/{account_id}/transactions/",
            params=params
        )


class TinkProvider(BankProviderClient):
    """Tink implementation for Open Banking (Czech banks and more)."""
    
    def __init__(self):
        self.base_url = settings.TINK_API_URL
        self.client_id = settings.TINK_CLIENT_ID
        self.client_secret = settings.TINK_CLIENT_SECRET
        self._client_token = None
        self._client_token_expires_at = None
        self._user_token = None
        self._user_token_expires_at = None
    
    async def _get_client_token(self) -> str:
        """Get or refresh client credentials token."""
        if self._client_token and self._client_token_expires_at and datetime.utcnow() < self._client_token_expires_at:
            return self._client_token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "providers:read user:create authorization:grant"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            data = response.json()
            self._client_token = data["access_token"]
            # Token expires in seconds (typically 1800 = 30 mins)
            expires_in = data.get("expires_in", 1800)
            self._client_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            return self._client_token
    
    def set_user_token(self, token: str, expires_in: Optional[int] = None) -> None:
        """Set the user access token to be used for API requests."""
        self._user_token = token
        if expires_in:
            self._user_token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))
        else:
            self._user_token_expires_at = None
    
    async def _get_user_token(self) -> str:
        """Return currently set user access token."""
        if self._user_token and self._user_token_expires_at and datetime.utcnow() < self._user_token_expires_at:
            return self._user_token
        if self._user_token:
            return self._user_token
        raise RuntimeError("Tink user access token not set")
    
    async def create_tink_user(self, market: str = "CZ", external_user_id: Optional[str] = None) -> str:
        """Create a Tink user for a given market."""
        client_token = await self._get_client_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/user/create",
                headers={
                    "Authorization": f"Bearer {client_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "external_user_id": external_user_id or f"user_{datetime.utcnow().timestamp()}",
                    "market": market,
                    "locale": "cs_CZ" if market == "CZ" else f"{market.lower()}_{market}"
                }
            )
            
            # Handle 409 Conflict - user already exists
            if response.status_code == 409:
                # User exists, extract user_id from response if available
                try:
                    error_data = response.json()
                    # Tink may return existing user_id in error response
                    if "user_id" in error_data:
                        print(f"Tink user already exists, reusing: {error_data['user_id']}")
                        return error_data["user_id"]
                except:
                    pass
                # If no user_id in response, we can't proceed
                raise ValueError(f"Tink user with external_id '{external_user_id}' already exists but user_id not returned. Try different external_id or delete existing user.")
            
            response.raise_for_status()
            data = response.json()
            return data["user_id"]
    
    async def get_authorization_grant(self, user_id: str) -> str:
        """Get authorization grant code for a user."""
        client_token = await self._get_client_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/oauth/authorization-grant",
                headers={"Authorization": f"Bearer {client_token}"},
                data={
                    "user_id": user_id,
                    "scope": "accounts:read,transactions:read,balances:read,credentials:read,credentials:write,user:read"
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["code"]
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization grant code for user access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "code": code
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
    
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """List available institutions for a country."""
        async with httpx.AsyncClient() as client:
            # Public endpoint - no auth needed
            response = await client.get(
                f"{self.base_url}/api/v1/providers/{country}"
            )
            response.raise_for_status()
            data = response.json()
            providers = data.get("providers", [])
        
        # Map to common format
        return [
            {
                "id": p.get("name", ""),  # Tink uses 'name' as provider identifier
                "name": p.get("displayName", p.get("name", "")),
                "country": country,
                "logo": p.get("images", {}).get("icon", "") if isinstance(p.get("images"), dict) else ""
            }
            for p in providers
        ]
    
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None,
        user_id_external: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new requisition/consent (Tink credentials flow).
        
        For Tink SANDBOX, we use the Authorization Grant flow (backend-only).
        This creates a Tink user, gets an authorization grant, and returns
        the grant code that can be exchanged for a user token.
        
        For PRODUCTION, you would use Tink Link SDK instead.
        """
        # Note: institution_id is the Tink provider name (e.g., "cz-airbank-ob")
        
        try:
            # Step 1: Get client token
            client_token = await self._get_client_token()
            
            # Step 2: Create Tink user for this connection
            # Use timestamp-based external_id to ensure uniqueness and avoid 409 conflicts
            timestamp = datetime.utcnow().timestamp()
            external_id = f"{user_id_external}_{timestamp}" if user_id_external else f"wealthtracker_{reference}_{timestamp}"
            
            print(f"Creating Tink user with external_id: {external_id}")
            user_id = await self.create_tink_user(market="CZ", external_user_id=external_id)
            print(f"Tink user created: {user_id}")
            
            # Step 3: Get authorization grant code
            grant_code = await self.get_authorization_grant(user_id)
            print(f"Authorization grant obtained: {grant_code[:20]}...")
            
            return {
                "id": f"tink_{reference or institution_id}",
                "status": "created",
                "institution_id": institution_id,
                "reference": reference or "",
                "created": datetime.utcnow().isoformat(),
                "tink_user_id": user_id,
                "grant_code": grant_code,  # Authorization grant code to exchange for token
                "flow_type": "authorization_grant"  # Indicate this is backend flow
            }
        except Exception as e:
            # Log the full error for debugging
            print(f"ERROR in create_requisition: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Fall back to deferred flow if user creation fails
            return {
                "id": f"tink_{reference or institution_id}",
                "status": "error",
                "institution_id": institution_id,
                "reference": reference or "",
                "created": datetime.utcnow().isoformat(),
                "error": str(e),
                "flow_type": "deferred"
            }
    
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Get requisition details (checks credential status for Tink)."""
        # For Tink, requisition_id would be mapped to credentials_id
        # This is a simplified implementation
        return {
            "id": requisition_id,
            "status": "linked",
            "accounts": [],
        }
    
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """List accounts for user."""
        user_token = await self._get_user_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/accounts/list",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            response.raise_for_status()
            data = response.json()
            accounts = data.get("accounts", [])
            return [acc["id"] for acc in accounts]
    
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Get account details."""
        user_token = await self._get_user_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/accounts/{account_id}",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            response.raise_for_status()
            account = response.json()
        
        return {
            "id": account_id,
            "iban": account.get("identifiers", {}).get("iban", ""),
            "currency": account.get("currencyCode", ""),
            "name": account.get("name", f"Account {account_id[:8]}"),
            "ownerName": account.get("holderName", ""),
            "account_type": account.get("type", ""),
        }
    
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Get account balances."""
        user_token = await self._get_user_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/accounts/{account_id}",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            response.raise_for_status()
            account = response.json()
        
        # Extract balance from account data
        balance_amount = account.get("balance", 0)
        currency = account.get("currencyCode", "")
        
        return {
            "balances": [
                {
                    "balanceAmount": {
                        "amount": str(balance_amount),
                        "currency": currency
                    },
                    "balanceType": "expected",
                    "referenceDate": datetime.utcnow().date().isoformat(),
                }
            ]
        }
    
    async def get_transactions(
        self, 
        account_id: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get account transactions."""
        user_token = await self._get_user_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/transactions",
                headers={"Authorization": f"Bearer {user_token}"},
                params={"accountId": account_id}
            )
            response.raise_for_status()
            data = response.json()
            transactions_data = data.get("transactions", [])
        
        # Convert Tink format to our standard format
        booked = []
        for tx in transactions_data:
            amount = tx.get("amount", {}).get("value", {}).get("unscaledValue", 0)
            scale = tx.get("amount", {}).get("value", {}).get("scale", 0)
            actual_amount = amount / (10 ** scale) if scale else amount
            
            booked.append({
                "transactionId": tx.get("id", ""),
                "bookingDate": tx.get("dates", {}).get("booked", "")[:10] if tx.get("dates", {}).get("booked") else datetime.utcnow().date().isoformat(),
                "valueDate": tx.get("dates", {}).get("value", "")[:10] if tx.get("dates", {}).get("value") else None,
                "transactionAmount": {
                    "amount": str(actual_amount),
                    "currency": tx.get("amount", {}).get("currencyCode", "")
                },
                "creditorName": tx.get("counterparties", [{}])[0].get("name") if tx.get("type") == "DEBIT" else None,
                "debtorName": tx.get("counterparties", [{}])[0].get("name") if tx.get("type") == "CREDIT" else None,
                "remittanceInformationUnstructured": tx.get("descriptions", {}).get("original", ""),
            })
        
        return {
            "transactions": {
                "booked": booked,
                "pending": []
            }
        }


def get_bank_provider() -> BankProviderClient:
    """Get the configured bank provider instance."""
    # Use Tink if credentials are configured
    if settings.TINK_CLIENT_ID and settings.TINK_CLIENT_SECRET:
        return TinkProvider()
    
    # Use TrueLayer if credentials are configured
    if settings.TRUELAYER_CLIENT_ID and settings.TRUELAYER_CLIENT_SECRET:
        return TrueLayerProvider()
    
    # Fall back to GoCardless if configured
    if settings.GOCARDLESS_SECRET_ID and settings.GOCARDLESS_SECRET_KEY:
        return GoCardlessProvider()
    
    # Use mock provider if no credentials configured
    return MockBankProvider()
