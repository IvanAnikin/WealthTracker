"""
Tink Integration Test
Tests the complete Tink OAuth flow and data access for Czech banks.
"""
import os
import httpx
import json
from datetime import datetime, timedelta

# Get credentials from environment
TINK_CLIENT_ID = os.getenv("TINK_CLIENT_ID")
TINK_CLIENT_SECRET = os.getenv("TINK_CLIENT_SECRET")
TINK_API_URL = os.getenv("TINK_API_URL", "https://api.tink.com")

def check_credentials():
    """Verify Tink credentials are set."""
    if not TINK_CLIENT_ID or not TINK_CLIENT_SECRET:
        print("❌ Set TINK_CLIENT_ID and TINK_CLIENT_SECRET env vars")
        return False
    print(f"✅ Credentials loaded: {TINK_CLIENT_ID}")
    return True


async def get_client_token() -> str:
    """Get a client credentials token for API access."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TINK_API_URL}/api/v1/oauth/token",
            data={
                "client_id": TINK_CLIENT_ID,
                "client_secret": TINK_CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "providers:read user:create authorization:grant"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


async def list_providers(client_token: str, market: str = "CZ") -> list:
    """List available providers for a market."""
    async with httpx.AsyncClient() as client:
        # Public endpoint - no auth needed
        resp = await client.get(
            f"{TINK_API_URL}/api/v1/providers/{market}"
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("providers", [])


async def create_user(client_token: str, market: str = "CZ") -> str:
    """Create a Tink user for testing."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TINK_API_URL}/api/v1/user/create",
            headers={
                "Authorization": f"Bearer {client_token}",
                "Content-Type": "application/json"
            },
            json={
                "external_user_id": f"test_user_{datetime.utcnow().timestamp()}",
                "market": market,
                "locale": "cs_CZ" if market == "CZ" else f"{market.lower()}_{market}"
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["user_id"]


async def get_user_token(client_token: str, user_id: str) -> str:
    """Get a user-scoped token for data access.
    
    Tink uses a 2-step process:
    1. Create authorization grant for the user
    2. Exchange grant code for user access token
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Get authorization grant code
        resp = await client.post(
            f"{TINK_API_URL}/api/v1/oauth/authorization-grant",
            headers={"Authorization": f"Bearer {client_token}"},
            data={
                "user_id": user_id,
                "scope": "accounts:read,transactions:read,balances:read,credentials:read,user:read"
            }
        )
        resp.raise_for_status()
        grant_data = resp.json()
        auth_code = grant_data["code"]
        
        # Step 2: Exchange code for user access token
        resp2 = await client.post(
            f"{TINK_API_URL}/api/v1/oauth/token",
            data={
                "client_id": TINK_CLIENT_ID,
                "client_secret": TINK_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": auth_code
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp2.raise_for_status()
        token_data = resp2.json()
        return token_data["access_token"]


async def authenticate_to_provider(client_token: str, user_id: str, provider_id: str, credentials: dict) -> str:
    """Create credentials (connect to provider) for a user."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TINK_API_URL}/api/v1/credentials",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "user_id": user_id,
                "provider_id": provider_id,
                "fields": [
                    {
                        "name": "username",
                        "value": credentials.get("username", "testuser")
                    },
                    {
                        "name": "password",
                        "value": credentials.get("password", "testpass")
                    }
                ]
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["id"]


async def get_accounts(user_token: str) -> list:
    """List accounts for the authenticated user."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TINK_API_URL}/api/v1/accounts/list",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("accounts", [])


async def get_transactions(user_token: str, account_id: str, days: int = 30) -> list:
    """Get transactions for an account."""
    date_from = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TINK_API_URL}/api/v1/transactions",
            headers={"Authorization": f"Bearer {user_token}"},
            params={
                "accountId": account_id,
                "pageSize": 100
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("transactions", [])


async def main():
    """Run full integration test."""
    print("=" * 60)
    print("🏦 Tink Integration Test")
    print("=" * 60)
    
    # Step 1: Check credentials
    print("\n1️⃣  Verifying credentials...")
    if not check_credentials():
        return
    
    try:
        # Step 2: Get client token
        print("\n2️⃣  Getting client token...")
        client_token = await get_client_token()
        print(f"✅ Client token: {client_token[:20]}...")
        
        # Step 3: List Czech providers
        print("\n3️⃣  Listing Czech (CZ) providers...")
        providers = await list_providers(client_token, "CZ")
        
        if not providers:
            print("⚠️  No providers found for CZ market")
            print("   Trying test providers instead...")
            # Try with test providers
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{TINK_API_URL}/api/v1/providers/CZ?excludeNonTestProviders=true&includeTestProviders=true"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    providers = data.get("providers", [])
        
        print(f"✅ Found {len(providers)} providers")
        for p in providers[:10]:  # Show first 10
            display_name = p.get('displayName', p.get('name', 'Unknown'))
            provider_name = p.get('name', p.get('providerName', ''))
            provider_type = p.get('type', '')
            print(f"   - {display_name} ({provider_name}) [{provider_type}]")
        
        # Step 4: Create a test user
        print("\n4️⃣  Creating test user...")
        user_id = await create_user(client_token)
        print(f"✅ User created: {user_id}")
        
        # Step 5: Get user token
        print("\n5️⃣  Getting user-scoped token...")
        user_token = await get_user_token(client_token, user_id)
        print(f"✅ User token: {user_token[:20]}...")
        
        # Step 6: Show provider example (using sandbox provider)
        print("\n6️⃣  Test credentials example...")
        if providers:
            test_provider = next((p for p in providers if p.get('type') == 'TEST'), providers[0] if providers else None)
            if test_provider:
                provider_name = test_provider.get('name', test_provider.get('providerName'))
                display_name = test_provider.get('displayName', provider_name)
                print(f"   Example provider: {display_name} ({provider_name})")
                print(f"\n   To authenticate, POST to /api/v1/credentials:")
                print(f"   {{")
                print(f"     \"providerName\": \"{provider_name}\",")
                print(f"     \"fields\": {{")
                print(f"       \"username\": \"tink\",  // for TEST providers")
                print(f"       \"password\": \"tink-1234\"")
                print(f"     }}")
                print(f"   }}")
                
                # Try creating test credentials
                if test_provider.get('type') == 'TEST':
                    print(f"\n   🧪 Attempting to create test credentials...")
                    try:
                        async with httpx.AsyncClient() as client:
                            cred_resp = await client.post(
                                f"{TINK_API_URL}/api/v1/credentials",
                                headers={
                                    "Authorization": f"Bearer {user_token}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "providerName": provider_name,
                                    "fields": {
                                        "username": "tink",
                                        "password": "tink-1234"
                                    }
                                }
                            )
                            if cred_resp.status_code in [200, 201]:
                                cred_data = cred_resp.json()
                                print(f"   ✅ Test credentials created: {cred_data.get('id')}")
                                print(f"   Status: {cred_data.get('status')}")
                            else:
                                print(f"   ⚠️  Credentials response: {cred_resp.status_code}")
                    except Exception as e:
                        print(f"   ⚠️  Could not create test credentials: {e}")
        
        print("\n" + "=" * 60)
        print("✅ Tink integration test completed!")
        print("=" * 60)
        print("\nKey findings:")
        print(f"- User token obtained successfully")
        print(f"- {len(providers)} providers available for CZ market")
        print(f"- Test providers available: {len([p for p in providers if p.get('type') == 'TEST'])}")
        print("\nNext steps:")
        print("1. Implement TinkProvider class in bank_provider.py")
        print("2. Use authorization grant flow for user tokens")
        print("3. Create credentials via /api/v1/credentials endpoint")
        print("4. Poll credential status until UPDATED")
        print("5. Fetch accounts and transactions")
        
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e.response.status_code}")
        try:
            error_data = e.response.json()
            print(f"   Details: {error_data}")
        except:
            print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
