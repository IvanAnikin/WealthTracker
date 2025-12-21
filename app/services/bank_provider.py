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
    """Mock implementation for testing with Czech bank data."""
    
    # Test credentials (Tink sandbox)
    TEST_CREDENTIALS = {
        "username": "u89799094",
        "password": "elv135"
    }
    
    async def list_institutions(self, country: str) -> List[Dict[str, Any]]:
        """Return mock institutions."""
        return [
            {
                "id": f"MOCK_BANK_{country}",
                "name": f"Mock Bank {country}",
                "country": country,
                "logo": "https://cdn-icons-png.flaticon.com/512/2830/2830284.png"
            }
        ]
    
    async def create_requisition(
        self, 
        institution_id: str, 
        redirect_url: str,
        reference: Optional[str] = None,
        user_id_external: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return mock requisition with authorization_grant flow."""
        req_id = f"req_mock_{int(datetime.utcnow().timestamp())}"
        # Simulate authorization grant flow (no redirect needed)
        return {
            "id": req_id,
            "status": "linked",
            "institution_id": institution_id,
            "reference": reference or "",
            "created": datetime.utcnow().isoformat(),
            "flow_type": "authorization_grant",
            "grant_code": f"mock_grant_{req_id}",
            "tink_user_id": f"mock_user_{user_id_external or 'default'}"
        }
    
    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Return mock requisition details."""
        return {
            "id": requisition_id,
            "status": "linked",
            "accounts": [f"acc_mock_checking_{requisition_id}", f"acc_mock_savings_{requisition_id}"],
        }
    
    async def list_accounts(self, requisition_id: str) -> List[str]:
        """Return mock account IDs."""
        return [f"acc_mock_checking_{requisition_id}", f"acc_mock_savings_{requisition_id}"]
    
    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Return mock account details."""
        is_savings = "savings" in account_id
        return {
            "id": account_id,
            "iban": "CZ6508000000192000145399" if not is_savings else "CZ9508000000192000145400",
            "currency": "CZK",
            "name": "Mock Savings Account" if is_savings else "Mock Checking Account",
            "ownerName": "Jan Novák",
        }
    
    async def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Return mock balances."""
        is_savings = "savings" in account_id
        amount = "45230.50" if is_savings else "12450.75"
        return {
            "balances": [
                {
                    "balanceAmount": {"amount": amount, "currency": "CZK"},
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
        """Return realistic Czech banking transactions for the past year."""
        is_savings = "savings" in account_id
        
        # Generate transactions for the whole year
        transactions = []
        today = datetime.utcnow()
        
        if is_savings:
            # Savings account: monthly deposits and interest
            for months_ago in range(12):
                tx_date = today - timedelta(days=30 * months_ago)
                tx_date_iso = tx_date.date().isoformat()
                
                transactions.append({
                    "transactionId": f"tx_savings_{months_ago * 2 + 1}",
                    "bookingDate": tx_date_iso,
                    "valueDate": tx_date_iso,
                    "transactionAmount": {"amount": "5000.00", "currency": "CZK"},
                    "creditorName": "Transfer from Checking",
                    "remittanceInformationUnstructured": "Monthly savings",
                })
                
                # Interest every other month
                if months_ago % 2 == 0:
                    transactions.append({
                        "transactionId": f"tx_savings_{months_ago * 2 + 2}",
                        "bookingDate": (tx_date - timedelta(days=15)).date().isoformat(),
                        "valueDate": (tx_date - timedelta(days=15)).date().isoformat(),
                        "transactionAmount": {"amount": "42.50", "currency": "CZK"},
                        "creditorName": "Československá obchodní banka",
                        "remittanceInformationUnstructured": "Interest payment",
                    })
        else:
            # Checking account: varied realistic transactions
            tx_id = 0
            
            # Generate daily transactions for the year
            for day_offset in range(365, -1, -1):
                tx_date = today - timedelta(days=day_offset)
                tx_date_iso = tx_date.date().isoformat()
                
                # Monthly salary on the 1st
                if tx_date.day == 1:
                    transactions.append({
                        "transactionId": f"tx_check_{tx_id}",
                        "bookingDate": tx_date_iso,
                        "valueDate": tx_date_iso,
                        "transactionAmount": {"amount": "45000.00", "currency": "CZK"},
                        "creditorName": "ABC Software s.r.o.",
                        "remittanceInformationUnstructured": f"Salary {tx_date.strftime('%B %Y')}",
                    })
                    tx_id += 1
                
                # Random everyday transactions (70% chance)
                if tx_id % 7 != 0:
                    # Groceries 20%
                    if tx_id % 5 == 0:
                        merchants = ["Albert Hypermarket", "Lidl", "Tesco", "Kaufland", "Penny"]
                        amounts = ["356.50", "289.00", "412.30", "195.50", "267.80"]
                        idx = hash(str(tx_id)) % len(merchants)
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amounts[idx]}", "currency": "CZK"},
                            "debtorName": merchants[idx],
                            "remittanceInformationUnstructured": "Groceries",
                        })
                        tx_id += 1
                    
                    # Utilities (monthly)
                    if tx_date.day == 15:
                        utilities = [
                            ("ČEZ Prodej", "1250.00", "Electricity bill"),
                            ("Vodafone Czech Republic", "450.00", "Mobile phone"),
                            ("O2 Czech Republic", "599.00", "Internet"),
                        ]
                        idx = (tx_date.month - 1) % len(utilities)
                        merchant, amount, desc = utilities[idx]
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amount}", "currency": "CZK"},
                            "debtorName": merchant,
                            "remittanceInformationUnstructured": desc,
                        })
                        tx_id += 1
                    
                    # Rent (monthly on 5th)
                    if tx_date.day == 5:
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": "-15000.00", "currency": "CZK"},
                            "debtorName": "Jana Dvořáková",
                            "remittanceInformationUnstructured": f"Rent {tx_date.strftime('%B %Y')}",
                        })
                        tx_id += 1
                    
                    # Transport
                    if tx_id % 9 == 0:
                        transports = [
                            ("Shell", "1450.00", "Fuel"),
                            ("Dopravní podnik hl. m. Prahy", "550.00", "Monthly ticket"),
                        ]
                        idx = hash(str(tx_id)) % len(transports)
                        merchant, amount, desc = transports[idx]
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amount}", "currency": "CZK"},
                            "debtorName": merchant,
                            "remittanceInformationUnstructured": desc,
                        })
                        tx_id += 1
                    
                    # Restaurants/Entertainment
                    if tx_id % 12 == 0:
                        restaurants = [
                            ("Lokál Dlouhááá", "350.00", "Dinner"),
                            ("Starbucks", "125.00", "Coffee"),
                            ("U Fleků", "680.00", "Dinner with friends"),
                            ("Cinema City", "240.00", "Movie tickets"),
                        ]
                        idx = hash(str(tx_id)) % len(restaurants)
                        merchant, amount, desc = restaurants[idx]
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amount}", "currency": "CZK"},
                            "debtorName": merchant,
                            "remittanceInformationUnstructured": desc,
                        })
                        tx_id += 1
                    
                    # Subscriptions (monthly)
                    if tx_date.day == 10:
                        subscriptions = [
                            ("Netflix", "199.00", "Subscription"),
                            ("Spotify", "139.00", "Premium subscription"),
                        ]
                        idx = (tx_date.month - 1) % len(subscriptions)
                        merchant, amount, desc = subscriptions[idx]
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amount}", "currency": "CZK"},
                            "debtorName": merchant,
                            "remittanceInformationUnstructured": desc,
                        })
                        tx_id += 1
                    
                    # Shopping
                    if tx_id % 20 == 0:
                        shops = [
                            ("H&M", "850.00", "Clothing"),
                            ("Alza.cz", "1299.00", "Electronics"),
                            ("Decathlon", "599.00", "Sports equipment"),
                        ]
                        idx = hash(str(tx_id)) % len(shops)
                        merchant, amount, desc = shops[idx]
                        transactions.append({
                            "transactionId": f"tx_check_{tx_id}",
                            "bookingDate": tx_date_iso,
                            "valueDate": tx_date_iso,
                            "transactionAmount": {"amount": f"-{amount}", "currency": "CZK"},
                            "debtorName": merchant,
                            "remittanceInformationUnstructured": desc,
                        })
                        tx_id += 1
        
        return {
            "transactions": {
                "booked": transactions,
                "pending": [
                    {
                        "transactionId": "tx_pending_1",
                        "bookingDate": datetime.utcnow().date().isoformat(),
                        "valueDate": datetime.utcnow().date().isoformat(),
                        "transactionAmount": {"amount": "-125.00", "currency": "CZK"},
                        "debtorName": "Starbucks",
                        "remittanceInformationUnstructured": "Coffee (pending)",
                    }
                ] if not is_savings else []
            }
        }
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Mock token exchange."""
        return {
            "access_token": f"mock_token_{code}",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    
    def set_user_token(self, token: str, expires_in: Optional[int] = None) -> None:
        """Mock token setter."""
        pass


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


def get_bank_provider(institution_id: Optional[str] = None) -> BankProviderClient:
    """Get the configured bank provider instance.
    
    Args:
        institution_id: Optional institution ID to check if it's a mock bank
    """
    # Always use Mock provider for mock banks
    if institution_id and institution_id.startswith("MOCK_BANK_"):
        return MockBankProvider()
    
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
