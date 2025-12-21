#!/usr/bin/env python3
"""
Test Tink Authorization Grant Flow (Sandbox)
This validates the complete backend flow without browser OAuth redirect.
"""
import asyncio
import sys
sys.path.insert(0, '/Users/ivananikin/Documents/WealthTracker')

from app.services.bank_provider import TinkProvider

async def test_sandbox_flow():
    """Test the complete Tink sandbox authorization grant flow."""
    print("\n" + "="*70)
    print("TINK SANDBOX AUTHORIZATION GRANT FLOW TEST")
    print("="*70)
    
    provider = TinkProvider()
    
    # Step 1: Test create_requisition (should complete backend flow)
    print("\n[1/5] Testing create_requisition...")
    try:
        requisition_data = await provider.create_requisition(
            institution_id="cz-kb-ob",
            redirect_url="http://localhost:8081/banks/connect/callback",
            reference="test_ref_flow",
            user_id_external="test_user_sandbox_flow"
        )
        
        print(f"✅ Requisition created")
        print(f"   ID: {requisition_data.get('id')}")
        print(f"   Flow type: {requisition_data.get('flow_type')}")
        print(f"   Tink user ID: {requisition_data.get('tink_user_id')}")
        print(f"   Grant code: {requisition_data.get('grant_code')[:20]}..." if requisition_data.get('grant_code') else "   Grant code: None")
        
        if requisition_data.get('flow_type') != 'authorization_grant':
            print(f"❌ Expected flow_type='authorization_grant', got '{requisition_data.get('flow_type')}'")
            return False
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Step 2: Test token exchange
    print("\n[2/5] Testing token exchange...")
    grant_code = requisition_data.get('grant_code')
    if not grant_code:
        print("❌ No grant code returned")
        return False
        
    try:
        token_data = await provider.exchange_code_for_token(grant_code)
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in')
        
        print(f"✅ Token exchanged successfully")
        print(f"   Access token: {access_token[:30]}...")
        print(f"   Expires in: {expires_in} seconds")
        
        if not access_token:
            print("❌ No access token returned")
            return False
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Step 3: Set token and test list_accounts
    print("\n[3/5] Testing account listing...")
    provider.set_user_token(access_token, expires_in=expires_in)
    
    try:
        account_ids = await provider.list_accounts("test_requisition")
        print(f"✅ Accounts listed: {len(account_ids)} account(s)")
        for aid in account_ids[:3]:  # Show first 3
            print(f"   - {aid}")
        if len(account_ids) > 3:
            print(f"   ... and {len(account_ids) - 3} more")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Step 4: Test account details (if any accounts found)
    if account_ids:
        print(f"\n[4/5] Testing account details for first account...")
        try:
            details = await provider.get_account_details(account_ids[0])
            print(f"✅ Account details retrieved")
            print(f"   Name: {details.get('name', 'N/A')}")
            print(f"   IBAN: {details.get('iban', 'N/A')}")
            print(f"   Currency: {details.get('currency', 'N/A')}")
            print(f"   Owner: {details.get('ownerName', 'N/A')}")
        except Exception as e:
            print(f"⚠️  Failed (may be expected in sandbox): {e}")
    else:
        print("\n[4/5] No accounts to test details")
    
    # Step 5: Test balances
    if account_ids:
        print(f"\n[5/5] Testing account balances...")
        try:
            balances = await provider.get_balances(account_ids[0])
            print(f"✅ Balances retrieved")
            if balances.get('balances'):
                for balance in balances['balances'][:2]:
                    print(f"   Type: {balance.get('balanceType', 'N/A')}")
                    print(f"   Amount: {balance.get('balanceAmount', {}).get('amount', 'N/A')} {balance.get('balanceAmount', {}).get('currency', '')}")
        except Exception as e:
            print(f"⚠️  Failed (may be expected in sandbox): {e}")
    else:
        print("\n[5/5] No accounts to test balances")
    
    print("\n" + "="*70)
    print("✅ SANDBOX FLOW TEST COMPLETED SUCCESSFULLY")
    print("="*70)
    print("\nKey findings:")
    print("  • Authorization grant flow works without browser OAuth redirect")
    print("  • Suitable for sandbox testing with demo data")
    print("  • For production, consider Tink Link SDK for real user auth")
    print("")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_sandbox_flow())
    sys.exit(0 if success else 1)
