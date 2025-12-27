import datetime
import httpx

BASE = "http://127.0.0.1:8081"
HEADERS = {}


def ensure_token():
    import time
    email = f"analysis_{int(time.time())}@example.com"
    password = "SecurePassword123!"
    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as client:
        try:
            client.post("/auth/register", json={"email": email, "password": password})
        except Exception:
            pass
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
        "exclude_internal_transfers": True,
    }
    if account_id:
        params["account_id"] = account_id
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60.0, follow_redirects=True) as client:
        r = client.get("/reports/categories", params=params)
        r.raise_for_status()
        return r.json()


def main():
    ensure_token()
    cats = fetch_categories(days=180)
    incomes = [c for c in cats if c.get("amount", 0) > 0]
    print("Global income categories (excluding internal transfers):")
    for c in sorted(incomes, key=lambda x: x["amount"], reverse=True)[:10]:
        print(f"{c.get('category_name','<unknown>'):30s} amount={c['amount']:,.2f} count={c.get('count', '?')}")


if __name__ == "__main__":
    main()
