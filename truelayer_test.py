import os
import sys
from urllib.parse import urlencode
import httpx

CLIENT_ID = os.getenv("TRUELAYER_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("TRUELAYER_CLIENT_SECRET", "").strip()
AUTH_URL = os.getenv("TRUELAYER_AUTH_URL", "https://auth.truelayer-sandbox.com").strip()
BASE_URL = os.getenv("TRUELAYER_BASE_URL", "https://api.truelayer-sandbox.com").strip()
REDIRECT_URI = os.getenv("TRUELAYER_REDIRECT_URI", "http://localhost:8081/banks/connect/callback").strip()
AUTH_CODE = os.getenv("TRUELAYER_AUTH_CODE", "").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("Missing TRUELAYER_CLIENT_ID / TRUELAYER_CLIENT_SECRET env vars.")
    sys.exit(1)

def list_providers(country="CZ"):
    params = {
        "clientId": CLIENT_ID,
        "country": country,
    }
    resp = httpx.get(f"{AUTH_URL}/api/providers", params=params, timeout=20)
    print("Providers status:", resp.status_code)
    if resp.status_code != 200:
        print("Providers error:", resp.text)
        sys.exit(2)
    data = resp.json()
    providers = data if isinstance(data, list) else data.get("results", [])
    print(f"Providers returned: {len(providers)}")
    for p in providers[:10]:
        print("-", p.get("display_name"), p.get("provider_id"), p.get("country_code"))
    return providers

def build_auth_url(provider_id=None, scopes="info accounts balance transactions"):
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": scopes,
    }
    if provider_id:
        params["providers"] = provider_id
    url = f"{AUTH_URL}/?{urlencode(params)}"
    print("Auth URL:", url)
    print("Open this URL in your browser, complete bank auth,",
          "then set TRUELAYER_AUTH_CODE env var to the returned 'code' and rerun.")
    return url

def exchange_code_for_token(code):
    resp = httpx.post(
        f"{AUTH_URL}/connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    print("Token (auth code) status:", resp.status_code)
    if resp.status_code != 200:
        print("Token error:", resp.text)
        sys.exit(3)
    data = resp.json()
    return data["access_token"]

def get_accounts(token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(f"{BASE_URL}/api/accounts", headers=headers, timeout=20)
    print("Accounts status:", resp.status_code)
    if resp.status_code != 200:
        print("Accounts error:", resp.text)
        sys.exit(4)
    data = resp.json()
    results = data.get("results", [])
    print(f"Accounts returned: {len(results)}")
    for a in results[:5]:
        print("-", a.get("display_name"), a.get("account_id"), a.get("currency"))
    return results

def get_balance(token, account_id):
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(f"{BASE_URL}/api/accounts/{account_id}/balance", headers=headers, timeout=20)
    print("Balance status:", resp.status_code)
    if resp.status_code != 200:
        print("Balance error:", resp.text)
        return None
    data = resp.json()
    print("Balance:", data)
    return data

def get_transactions(token, account_id, date_from=None, date_to=None):
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    resp = httpx.get(f"{BASE_URL}/api/accounts/{account_id}/transactions", headers=headers, params=params, timeout=30)
    print("Transactions status:", resp.status_code)
    if resp.status_code != 200:
        print("Transactions error:", resp.text)
        return None
    data = resp.json()
    results = data.get("results", [])
    print(f"Transactions returned: {len(results)}")
    for t in results[:5]:
        print("-", t.get("timestamp"), t.get("amount"), t.get("currency"), t.get("description"))
    return data

if __name__ == "__main__":
    # Step 1: list providers
    providers = list_providers("CZ")
    first_provider = providers[0]["provider_id"] if providers else None

    # Step 2: print auth URL for manual flow
    build_auth_url(first_provider)

    # Step 3: if AUTH_CODE provided, exchange and fetch accounts/balances/transactions
    if AUTH_CODE:
        user_token = exchange_code_for_token(AUTH_CODE)
        accounts = get_accounts(user_token)
        if accounts:
            acc_id = accounts[0]["account_id"]
            get_balance(user_token, acc_id)
            get_transactions(user_token, acc_id)
    else:
        print("Set TRUELAYER_AUTH_CODE to proceed with accounts and transactions testing.")