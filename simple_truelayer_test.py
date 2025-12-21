# truelayer_providers_test.py
import os
import httpx

CLIENT_ID = os.getenv("TRUELAYER_CLIENT_ID", "").strip()
AUTH_URL = os.getenv("TRUELAYER_AUTH_URL", "https://auth.truelayer-sandbox.com").strip()

def get_providers(country="CZ"):
    params = {
        "clientId": CLIENT_ID,  # filters to providers enabled for your app
        "country": country,     # ISO country code; you can pass multiple with space-separated list
        # "scopes": "info accounts balance transactions",  # optional filter, omit if unsure
    }
    resp = httpx.get(f"{AUTH_URL}/api/providers", params=params, timeout=20)
    print("Providers status:", resp.status_code)
    if resp.status_code != 200:
        print("Providers error:", resp.text)
        return []
    data = resp.json()
    # Response is a list of providers
    results = data if isinstance(data, list) else data.get("results", [])
    for p in results[:10]:
        print("-", p.get("display_name"), p.get("provider_id"), p.get("country_code"))
    return results

if __name__ == "__main__":
    if not CLIENT_ID:
        print("Set TRUELAYER_CLIENT_ID env var.")
    get_providers("CZ")