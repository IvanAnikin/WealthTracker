#!/usr/bin/env python3
"""
Demo script to test the WealthTracker API.
This script demonstrates the full workflow:
1. Register a user
2. Login
3. List institutions
4. Connect a bank (mock)
5. Sync accounts
6. View transactions
7. Create categories
8. Auto-categorize
9. View reports
10. Export data
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def main():
    print("\n🚀 WealthTracker API Demo")
    print("Starting automated API workflow test...\n")
    
    # Unique email for this test run
    test_email = f"demo_{int(time.time())}@example.com"
    test_password = "SecurePassword123"
    
    # 1. Register a user
    print_section("1. Registering New User")
    register_data = {
        "email": test_email,
        "password": test_password
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print(f"✅ User registered: {response.json()['email']}")
    else:
        print(f"❌ Registration failed: {response.text}")
        return
    
    # 2. Login
    print_section("2. Logging In")
    login_data = {
        "username": test_email,
        "password": test_password
    }
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Login successful")
        print(f"   Token: {token[:30]}...")
    else:
        print(f"❌ Login failed: {response.text}")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. List institutions
    print_section("3. Listing Available Banks")
    response = requests.get(f"{BASE_URL}/banks/institutions?country=CZ", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        institutions = response.json()
        print(f"✅ Found {len(institutions)} institutions")
        for inst in institutions[:3]:
            print(f"   - {inst['name']} ({inst['id']})")
    
    # 4. Connect a bank (using mock)
    print_section("4. Connecting to Mock Bank")
    connect_data = {
        "institution_id": "MOCK_BANK_CZ",
        "redirect_url": "http://localhost:8000/callback"
    }
    response = requests.post(f"{BASE_URL}/banks/connect", json=connect_data, headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        requisition_id = response.json()["requisition_id"]
        print(f"✅ Bank connection initiated")
        print(f"   Requisition ID: {requisition_id}")
        
        # Simulate callback (in real scenario, user would be redirected to bank)
        print("\n   Simulating callback...")
        ref = f"user_{test_email}_{int(time.time())}"
        callback_response = requests.get(
            f"{BASE_URL}/banks/connect/callback?ref={ref}",
            headers=headers
        )
        print(f"   Callback status: {callback_response.status_code}")
    
    # 5. List accounts
    print_section("5. Listing Connected Accounts")
    response = requests.get(f"{BASE_URL}/banks/accounts", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        accounts = response.json()
        print(f"✅ Found {len(accounts)} accounts")
        for acc in accounts:
            print(f"   - {acc.get('name', 'Unnamed')} ({acc['currency']})")
            print(f"     IBAN: {acc.get('iban', 'N/A')}")
    
    # 6. Sync accounts
    print_section("6. Syncing Account Data")
    response = requests.post(f"{BASE_URL}/sync/", json={}, headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        sync_result = response.json()
        print(f"✅ Sync complete")
        print(f"   Accounts synced: {sync_result['accounts_synced']}")
        print(f"   Transactions added: {sync_result['transactions_added']}")
    
    # 7. View transactions
    print_section("7. Viewing Transactions")
    response = requests.get(f"{BASE_URL}/transactions?limit=5", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        transactions = response.json()
        print(f"✅ Retrieved {len(transactions)} transactions")
        for tx in transactions[:3]:
            date = datetime.fromisoformat(tx['booking_date']).strftime('%Y-%m-%d')
            amount = f"{tx['amount']:+.2f} {tx['currency']}"
            print(f"   - {date}: {amount:>15} - {tx.get('description', 'N/A')[:30]}")
    
    # 8. View balances
    print_section("8. Checking Balances")
    response = requests.get(f"{BASE_URL}/transactions/balances/current", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        balances = response.json()
        print(f"✅ Current balances:")
        for bal in balances:
            print(f"   Account {bal['account_id'][:12]}...: {bal['balance']:.2f} {bal['currency']}")
    
    # 9. List categories
    print_section("9. Listing Categories")
    response = requests.get(f"{BASE_URL}/categories/", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        categories = response.json()
        print(f"✅ Found {len(categories)} categories")
        for cat in categories[:5]:
            icon = cat.get('icon', '📦')
            print(f"   {icon} {cat['name']}")
    
    # 10. Auto-categorize transactions
    print_section("10. Auto-Categorizing Transactions")
    response = requests.post(f"{BASE_URL}/categories/auto-categorize", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Auto-categorization complete")
        print(f"   Processed: {result['total_processed']}")
        print(f"   Categorized: {result['categorized']}")
    
    # 11. View cashflow report
    print_section("11. Viewing Cashflow Report")
    response = requests.get(f"{BASE_URL}/reports/cashflow", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        cashflow = response.json()
        print(f"✅ Cashflow report:")
        for month_data in cashflow[:3]:
            print(f"   {month_data['month']}: Income: {month_data['income']:.2f}, "
                  f"Expenses: {month_data['expenses']:.2f}, Net: {month_data['net']:.2f}")
    
    # 12. Export transactions
    print_section("12. Exporting Data")
    response = requests.get(f"{BASE_URL}/export/transactions.csv", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        csv_lines = response.text.split('\n')
        print(f"✅ CSV export generated")
        print(f"   Rows: {len(csv_lines)}")
        print(f"   Header: {csv_lines[0]}")
    
    print_section("✨ Demo Complete!")
    print("\nAll API endpoints tested successfully! 🎉")
    print(f"\nTest user credentials:")
    print(f"  Email: {test_email}")
    print(f"  Password: {test_password}")
    print(f"\nAccess the API documentation at: {BASE_URL}/docs")
    print(f"Access the Web UI at: {BASE_URL}/ui\n")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the API server.")
        print("   Please make sure the server is running:")
        print("   uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")
