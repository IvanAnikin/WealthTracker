#!/usr/bin/env python3
"""Test Tink OAuth URL generation."""
import asyncio
import sys
sys.path.insert(0, '/Users/ivananikin/Documents/WealthTracker')

from app.services.bank_provider import TinkProvider

async def test_oauth_url():
    provider = TinkProvider()
    
    # Test create_requisition to see if OAuth URL is properly generated
    requisition_data = await provider.create_requisition(
        institution_id="cz-airbank-ob",
        redirect_url="http://localhost:8081/banks/connect/callback",
        reference="test_ref_12345"
    )
    
    print("\n✅ Requisition created successfully")
    print(f"\nRequisition data:")
    print(f"  ID: {requisition_data.get('id')}")
    print(f"  Status: {requisition_data.get('status')}")
    print(f"  Reference: {requisition_data.get('reference')}")
    print(f"\n🔗 OAuth URL:")
    print(f"  {requisition_data.get('redirect_url')}")
    
    # Verify URL structure
    url = requisition_data.get('redirect_url', '')
    if url.startswith('https://oauth.tink.com/authorization?'):
        print("\n✅ OAuth URL has correct endpoint")
        if 'response_type=code' in url:
            print("✅ Contains response_type=code")
        if 'client_id=' in url:
            print("✅ Contains client_id")
        if 'scope=' in url:
            print("✅ Contains scope")
        if 'redirect_uri=' in url:
            print("✅ Contains redirect_uri")
        if 'state=test_ref_12345' in url:
            print("✅ Contains state with reference")
    else:
        print("\n❌ OAuth URL does not have correct endpoint")

if __name__ == "__main__":
    asyncio.run(test_oauth_url())
