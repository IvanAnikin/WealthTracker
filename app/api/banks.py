"""Bank connection API endpoints."""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
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
        inst_country = inst_data.get("countries", [country])[0] if isinstance(inst_data.get("countries"), list) else country
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
    provider = get_bank_provider()
    
    # Check if institution exists
    institution = db.query(Institution).filter(Institution.id == req_data.institution_id).first()
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    
    try:
        # Create requisition with provider
        reference = f"user_{current_user.id}_{datetime.utcnow().timestamp()}"
        requisition_data = await provider.create_requisition(
            req_data.institution_id,
            req_data.redirect_url,
            reference
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
        agreement_id=requisition_data.get("agreement"),
        redirect_url=req_data.redirect_url
    )
    db.add(requisition)
    db.commit()
    
    return {
        "requisition_id": requisition.id,
        "redirect_url": requisition_data.get("link") or requisition_data.get("redirect"),
        "status": "created"
    }


@router.get("/connect/callback")
async def connect_callback(
    ref: str = Query(..., description="Requisition reference"),
    db: Session = Depends(get_db)
):
    """Handle bank connection callback."""
    # Find requisition by reference
    requisition = db.query(Requisition).filter(Requisition.reference == ref).first()
    if not requisition:
        raise HTTPException(status_code=404, detail="Requisition not found")
    
    provider = get_bank_provider()
    
    try:
        # Get requisition status
        req_data = await provider.get_requisition(requisition.id)
        status = req_data.get("status")
        
        # Update requisition
        requisition.status = status
        if status == "linked" or status == "LN":
            requisition.linked_at = datetime.utcnow()
            
            # Get and save accounts
            account_ids = req_data.get("accounts", [])
            for account_id in account_ids:
                # Check if account already exists
                existing_account = db.query(Account).filter(Account.id == account_id).first()
                if not existing_account:
                    # Get account details
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
                        
                        # Sync initial balance and transactions
                        await sync_account_balances(db, provider, account_id)
                        await sync_account_transactions(db, provider, account_id)
                        
                    except Exception as e:
                        print(f"Failed to fetch account details for {account_id}: {e}")
        
        db.commit()
        
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
