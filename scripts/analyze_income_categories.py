import datetime
import httpx
from collections import defaultdict

BASE = "http://127.0.0.1:8081"
HEADERS = {}


def ensure_token():
    import time
    # Create a throwaway user and login to obtain a token
    email = f"analysis_{int(time.time())}@example.com"
    password = "SecurePassword123!"

    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as client:
        # Try register
        try:
            r = client.post("/auth/register", json={"email": email, "password": password})
            # 201 means created; 400 means exists (unlikely for unique email)
        except Exception:
            pass
        # Login
        r = client.post("/auth/login", data={"username": email, "password": password})
        r.raise_for_status()
        token = r.json().get("access_token")
        if not token:
            raise RuntimeError("Login did not return access_token")
        HEADERS["Authorization"] = f"Bearer {token}"


def fetch_categories(days: int = 180, account_id: str | None = None):
    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(days=days)
    params = {
        "start_date": f"{start.date().isoformat()}T00:00:00Z",
        "end_date": f"{end.date().isoformat()}T23:59:59Z",
    }
    if account_id:
        params["account_id"] = account_id
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60.0, follow_redirects=True) as client:
        r = client.get("/reports/categories", params=params)
        r.raise_for_status()
        return r.json()


def fetch_accounts():
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        r = client.get("/reports/accounts/list")
        r.raise_for_status()
        return r.json()


def main():
    ensure_token()
    # Load accounts to map account_id -> name
    account_map = {}
    try:
        accounts = fetch_accounts()
        for a in (accounts.get("accounts") or []):
            account_map[str(a.get("id"))] = a.get("name") or str(a.get("id"))
    except Exception as e:
        print("Warning: could not fetch accounts:", e)

    # Global income categories
    global_cats = fetch_categories(days=180)
    incomes_global = [c for c in global_cats if c.get("amount", 0) > 0]
    print("\n=== Global income categories (top 10) ===")
    for c in sorted(incomes_global, key=lambda x: x["amount"], reverse=True)[:10]:
        print(f"{c.get('category_name','<unknown>'):30s} amount={c['amount']:,.2f} count={c.get('count', '?')}")

    # Per-account income categories
    for acc_id, acc_name in account_map.items():
        cats = fetch_categories(days=180, account_id=acc_id)
        incomes = [c for c in cats if c.get("amount", 0) > 0]
        if not incomes:
            continue
        print(f"\n=== Income categories for account {acc_id} ({acc_name}) ===")
        for c in sorted(incomes, key=lambda x: x["amount"], reverse=True)[:10]:
            print(f"{c.get('category_name','<unknown>'):30s} amount={c['amount']:,.2f} count={c.get('count', '?')}")


if __name__ == "__main__":
    main()
