"""Bank connection API endpoints."""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Institution, Requisition, Account
from app.schemas import InstitutionResponse, RequisitionCreate, RequisitionResponse, AccountResponse
from app.api.auth import get_current_user
from app.services.bank_provider import get_bank_provider
from app.services.sync_service import sync_account_balances, sync_account_transactions

router = APIRouter(prefix="/banks", tags=["Bank Connection"])


@router.get("/institutions", response_model=List[InstitutionResponse])
async def list_institutions(
    country: str = Query("CZ", description="Two-letter country code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available bank institutions for a country."""
    provider = get_bank_provider()
    
    try:
        institutions_data = await provider.list_institutions(country)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch institutions: {str(e)}")
    
    # Update database with institutions
    institutions = []
    for inst_data in institutions_data:
        inst_id = inst_data.get("id")
        inst_name = inst_data.get("name")
        # Support both GoCardless ('countries') and TrueLayer ('country') formats
        inst_country = (
            inst_data.get("country") or (
                inst_data.get("countries", [country])[0]
                if isinstance(inst_data.get("countries"), list)
                else country
            )
        )
        logo_url = inst_data.get("logo")
        
        # Check if institution exists
        institution = db.query(Institution).filter(Institution.id == inst_id).first()
        if not institution:
            institution = Institution(
                id=inst_id,
                name=inst_name,
                country=inst_country,
                logo_url=logo_url
            )
            db.add(institution)
        else:
            # Update if needed
            institution.name = inst_name
            institution.logo_url = logo_url
        
        institutions.append(institution)
    
    db.commit()
    return institutions


@router.post("/connect", response_model=dict)
async def connect_bank(
    req_data: RequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initiate bank connection flow."""
    provider = get_bank_provider(institution_id=req_data.institution_id)
    
    # Check if institution exists, if not create it (for mock banks)
    institution = db.query(Institution).filter(Institution.id == req_data.institution_id).first()
    if not institution:
        # Auto-create institution for mock banks
        if req_data.institution_id.startswith("MOCK_BANK_"):
            country = req_data.institution_id.replace("MOCK_BANK_", "")
            institution = Institution(
                id=req_data.institution_id,
                name=f"Mock Bank {country}",
                country=country,
                logo_url="https://cdn-icons-png.flaticon.com/512/2830/2830284.png"
            )
            db.add(institution)
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Institution not found")
    
    try:
        # Create requisition with provider
        reference = f"user_{current_user.id}_{datetime.utcnow().timestamp()}"
        requisition_data = await provider.create_requisition(
            req_data.institution_id,
            req_data.redirect_url,
            reference,
            user_id_external=f"wealthtracker_{current_user.id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create requisition: {str(e)}")
    
    # Save requisition to database
    requisition = Requisition(
        id=requisition_data.get("id"),
        user_id=current_user.id,
        institution_id=req_data.institution_id,
        status="created",
        reference=reference,
        agreement_id=requisition_data.get("tink_user_id"),  # Store Tink user_id
        redirect_url=req_data.redirect_url
    )
    db.add(requisition)
    db.commit()
    
    # Check if this is Tink with authorization grant flow (sandbox backend-only flow)
    if hasattr(provider, "exchange_code_for_token") and requisition_data.get("flow_type") == "authorization_grant":
        # Tink sandbox: complete authorization immediately
        grant_code = requisition_data.get("grant_code")
        if not grant_code:
            error_msg = requisition_data.get("error", "Unknown error during authorization")
            print(f"ERROR: No grant code returned. Error: {error_msg}")
            return {
                "requisition_id": requisition.id,
                "status": "error",
                "error": error_msg,
                "message": f"Failed to connect: {error_msg}",
                "flow_type": "authorization_grant"
            }
            
        try:
            # Exchange grant code for user token
            token_data = await provider.exchange_code_for_token(grant_code)
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            
            if not access_token:
                raise ValueError("No access_token in token response")
            
            # Update requisition with token
            requisition.access_token = access_token
            if expires_in:
                requisition.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, int(expires_in) - 60))
            requisition.status = "linked"
            requisition.linked_at = datetime.utcnow()
            db.commit()
            
            # Set token on provider
            provider.set_user_token(access_token, expires_in=expires_in)
            
            # Fetch accounts
            try:
                account_ids = await provider.list_accounts(requisition.id)
                print(f"Found {len(account_ids)} accounts")
                for account_id in account_ids:
                    existing_account = db.query(Account).filter(Account.id == account_id).first()
                    if not existing_account:
                        try:
                            details = await provider.get_account_details(account_id)
                            account = Account(
                                id=account_id,
                                user_id=current_user.id,
                                institution_id=req_data.institution_id,
                                requisition_id=requisition.id,
                                iban=details.get("iban"),
                                currency=details.get("currency", "EUR"),
                                name=details.get("name"),
                                owner_name=details.get("ownerName")
                            )
                            db.add(account)
                            db.flush()
                            await sync_account_balances(db, provider, account_id)
                            await sync_account_transactions(db, provider, account_id)
                        except Exception as e:
                            print(f"Failed to fetch account {account_id}: {e}")
                db.commit()
            except Exception as e:
                print(f"Failed to fetch accounts: {e}")
            
            return {
                "requisition_id": requisition.id,
                "status": "linked",
                "message": "Bank connected successfully (sandbox test data)",
                "flow_type": "authorization_grant"
            }
        except Exception as e:
            error_msg = str(e)
            print(f"Failed to complete authorization: {error_msg}")
            return {
                "requisition_id": requisition.id,
                "status": "error",
                "error": error_msg,
                "message": f"Failed to exchange token: {error_msg}",
                "flow_type": "authorization_grant"
            }
    
    return {
        "requisition_id": requisition.id,
        "redirect_url": requisition_data.get("redirect_url") or requisition_data.get("link") or requisition_data.get("redirect"),
        "status": "created",
        "flow_type": requisition_data.get("flow_type", "redirect")
    }


@router.get("/connect/callback")
async def connect_callback(
    code: str = Query(None, description="Authorization code (TrueLayer/Tink)"),
    state: str = Query(None, description="Opaque state carrying reference (TrueLayer/Tink)"),
    ref: str = Query(None, description="Requisition reference (GoCardless)"),
    db: Session = Depends(get_db)
):
    """Handle bank connection callback for Tink, TrueLayer, or GoCardless.
    
    - Tink/TrueLayer: expects `code` and `state` (used as requisition reference).
    - GoCardless: expects `ref` and uses requisition status/accounts from provider.
    """
    # Resolve reference - state is used for Tink/TrueLayer
    reference = state or ref
    
    # If no code or reference yet, just show a waiting page
    if not reference and not code:
        return HTMLResponse("""
        <html>
        <head>
            <title>Bank Connection - Waiting</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; margin: 0; padding: 2rem; background: #f5f5f5; }
                .container { max-width: 600px; margin: 2rem auto; text-align: center; }
                .spinner { display: inline-block; border: 4px solid #ecf0f1; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                h2 { color: #2c3e50; }
                p { color: #7f8c8d; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="spinner"></div>
                <h2>Waiting for Bank Authorization...</h2>
                <p>Please complete the bank login on the other page.</p>
                <p style="font-size: 0.9rem; color: #95a5a6;">This page will automatically update once you authorize.</p>
            </div>
            <script>
                // Retry polling the callback every 2 seconds
                let attempts = 0;
                const checkStatus = () => {
                    attempts++;
                    if (attempts > 30) {  // Stop after 1 minute
                        document.body.innerHTML = '<div style="padding: 2rem; text-align: center;"><h2>Connection timeout</h2><p><a href="/ui/banks/connect">Try again</a></p></div>';
                        return;
                    }
                    setTimeout(() => window.location.reload(), 2000);
                };
                checkStatus();
            </script>
        </body>
        </html>
        """)
    
    if not reference:
        raise HTTPException(status_code=400, detail="Missing callback parameters: provide code+state (Tink/TrueLayer) or ref (GoCardless)")

    requisition = db.query(Requisition).filter(Requisition.reference == reference).first()
    if not requisition:
        raise HTTPException(status_code=404, detail="Requisition not found")

    provider = get_bank_provider()

    try:
        # Tink path: Exchange authorization code for user token
        if code and hasattr(provider, "get_authorization_grant"):
            # This is Tink provider (has get_authorization_grant method)
            # The 'code' here is from Tink's OAuth callback, we exchange it directly for a user token
            try:
                # Exchange the authorization code for access token
                token_data = await provider.exchange_code_for_token(code)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to authenticate with Tink: {e}")

            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            if not access_token:
                raise HTTPException(status_code=500, detail="No access_token returned from Tink")

            # Store tokens on requisition
            requisition.access_token = access_token
            if expires_in:
                requisition.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, int(expires_in) - 60))
            requisition.status = "linked"
            requisition.linked_at = datetime.utcnow()
            db.commit()

            # Set user token on provider for subsequent calls
            provider.set_user_token(access_token, expires_in=expires_in)

            # Fetch accounts via Tink
            try:
                account_ids = await provider.list_accounts(requisition.id)
                for account_id in account_ids:
                    existing_account = db.query(Account).filter(Account.id == account_id).first()
                    if not existing_account:
                        try:
                            details = await provider.get_account_details(account_id)
                            account = Account(
                                id=account_id,
                                user_id=requisition.user_id,
                                institution_id=requisition.institution_id,
                                requisition_id=requisition.id,
                                iban=details.get("iban"),
                                currency=details.get("currency", "EUR"),
                                name=details.get("name"),
                                owner_name=details.get("ownerName")
                            )
                            db.add(account)
                            db.flush()
                            await sync_account_balances(db, provider, account_id)
                            await sync_account_transactions(db, provider, account_id)
                        except Exception as e:
                            print(f"Failed to fetch account details for {account_id}: {e}")
                db.commit()
            except Exception as e:
                print(f"Failed to fetch accounts: {e}")

            return HTMLResponse("""
            <html>
            <head>
                <title>Bank Connection Successful</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; margin: 0; padding: 2rem; background: #f5f5f5; }
                    .container { max-width: 600px; margin: 2rem auto; text-align: center; padding: 2rem; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                    .success { color: #27ae60; font-size: 3rem; margin-bottom: 1rem; }
                    h2 { color: #2c3e50; margin: 0; }
                    p { color: #7f8c8d; margin: 1rem 0; }
                    a { color: #3498db; text-decoration: none; padding: 0.5rem 1rem; display: inline-block; border-radius: 4px; background: #ecf0f1; margin-top: 1rem; }
                    a:hover { background: #d5dbdb; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅</div>
                    <h2>Bank Connected Successfully!</h2>
                    <p>Your accounts are now connected and visible in WealthTracker.</p>
                    <a href="/ui/accounts">View Your Accounts →</a>
                </div>
            </body>
            </html>
            """)

        # TrueLayer path: exchange code for token, then fetch accounts
        if code and hasattr(provider, "exchange_code_for_token") and not hasattr(provider, "get_authorization_grant"):
            try:
                token_data = await provider.exchange_code_for_token(code, requisition.redirect_url or "")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to exchange code: {e}")

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            if not access_token:
                raise HTTPException(status_code=500, detail="No access_token returned from provider")

            # Store tokens on requisition
            requisition.access_token = access_token
            requisition.refresh_token = refresh_token
            if expires_in:
                requisition.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, int(expires_in) - 60))
            requisition.status = "linked"
            requisition.linked_at = datetime.utcnow()
            db.commit()

            # Use token for subsequent API calls
            if hasattr(provider, "set_user_token"):
                provider.set_user_token(access_token, expires_in=expires_in)

            # Fetch accounts via TrueLayer
            account_ids = await provider.list_accounts(requisition.id)
            for account_id in account_ids:
                existing_account = db.query(Account).filter(Account.id == account_id).first()
                if not existing_account:
                    try:
                        details = await provider.get_account_details(account_id)
                        account = Account(
                            id=account_id,
                            user_id=requisition.user_id,
                            institution_id=requisition.institution_id,
                            requisition_id=requisition.id,
                            iban=details.get("iban"),
                            currency=details.get("currency", "EUR"),
                            name=details.get("name"),
                            owner_name=details.get("ownerName")
                        )
                        db.add(account)
                        db.flush()
                        await sync_account_balances(db, provider, account_id)
                        await sync_account_transactions(db, provider, account_id)
                    except Exception as e:
                        print(f"Failed to fetch account details for {account_id}: {e}")

            db.commit()

            return {"status": requisition.status, "message": "Bank connection successful"}

        # GoCardless path: legacy requisition status/accounts
        req_data = await provider.get_requisition(requisition.id)
        status = req_data.get("status")
        requisition.status = status
        if status == "linked" or status == "LN":
            requisition.linked_at = datetime.utcnow()
            account_ids = req_data.get("accounts", [])
            for account_id in account_ids:
                existing_account = db.query(Account).filter(Account.id == account_id).first()
                if not existing_account:
                    try:
                        account_details = await provider.get_account_details(account_id)
                        account_info = account_details.get("account", {})
                        account = Account(
                            id=account_id,
                            user_id=requisition.user_id,
                            institution_id=requisition.institution_id,
                            requisition_id=requisition.id,
                            iban=account_info.get("iban"),
                            currency=account_info.get("currency", "EUR"),
                            name=account_info.get("name") or account_info.get("product"),
                            owner_name=account_info.get("ownerName")
                        )
                        db.add(account)
                        db.flush()
                        await sync_account_balances(db, provider, account_id)
                        await sync_account_transactions(db, provider, account_id)
                    except Exception as e:
                        print(f"Failed to fetch account details for {account_id}: {e}")
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process callback: {str(e)}")

    return {
        "status": requisition.status,
        "message": "Bank connection successful" if requisition.status in ["linked", "LN"] else "Connection pending"
    }


@router.get("/requisitions", response_model=List[RequisitionResponse])
def list_requisitions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's bank requisitions."""
    requisitions = db.query(Requisition).filter(
        Requisition.user_id == current_user.id
    ).order_by(Requisition.created_at.desc()).all()
    
    return requisitions


@router.delete("/requisitions/{requisition_id}")
async def disconnect_bank(
    requisition_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disconnect a bank connection."""
    requisition = db.query(Requisition).filter(
        Requisition.id == requisition_id,
        Requisition.user_id == current_user.id
    ).first()
    
    if not requisition:
        raise HTTPException(status_code=404, detail="Requisition not found")
    
    # Update status to revoked
    requisition.status = "revoked"
    db.commit()
    
    return {"message": "Bank connection revoked successfully"}


@router.delete("/requisitions")
async def disconnect_all_banks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disconnect all bank connections for the current user."""
    # Get all requisitions for user
    requisitions = db.query(Requisition).filter(
        Requisition.user_id == current_user.id
    ).all()
    
    count = len(requisitions)
    
    # Mark all as revoked
    for req in requisitions:
        req.status = "revoked"
    
    # Delete all accounts for this user
    db.query(Account).filter(Account.user_id == current_user.id).delete()
    
    db.commit()
    
    return {"message": f"Disconnected {count} bank connection(s) and removed all accounts"}


@router.get("/accounts", response_model=List[AccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's bank accounts."""
    accounts = db.query(Account).filter(
        Account.user_id == current_user.id
    ).order_by(Account.created_at.desc()).all()
    
    return accounts
