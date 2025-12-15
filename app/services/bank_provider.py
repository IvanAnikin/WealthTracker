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


def get_bank_provider() -> BankProviderClient:
    """Get the configured bank provider instance."""
    # Use mock provider if credentials are not configured
    if not settings.GOCARDLESS_SECRET_ID or not settings.GOCARDLESS_SECRET_KEY:
        return MockBankProvider()
    return GoCardlessProvider()
