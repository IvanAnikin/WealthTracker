"""Sync API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Account
from app.schemas import SyncRequest, SyncResponse
from app.api.auth import get_current_user
from app.services.bank_provider import get_bank_provider
from app.services.sync_service import sync_account_transactions, sync_account_balances, sync_all_user_accounts

router = APIRouter(prefix="/sync", tags=["Synchronization"])


@router.post("/", response_model=SyncResponse)
async def sync_accounts(
    sync_req: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger account synchronization."""
    provider = get_bank_provider()
    
    if sync_req.account_id:
        # Sync specific account
        account = db.query(Account).filter(
            Account.id == sync_req.account_id,
            Account.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Sync balance
        balance_result = await sync_account_balances(db, provider, account.id)
        if "error" in balance_result:
            raise HTTPException(status_code=500, detail=balance_result["error"])
        
        # Sync transactions
        tx_result = await sync_account_transactions(db, provider, account.id)
        if "error" in tx_result:
            raise HTTPException(status_code=500, detail=tx_result["error"])
        
        return SyncResponse(
            status="success",
            accounts_synced=1,
            transactions_added=tx_result.get("transactions_added", 0),
            message=f"Account {account.id} synced successfully"
        )
    else:
        # Sync all accounts
        result = await sync_all_user_accounts(db, provider, current_user.id)
        
        return SyncResponse(
            status=result["status"],
            accounts_synced=result["accounts_synced"],
            transactions_added=result["transactions_added"],
            message=f"Synced {result['accounts_synced']} of {result['total_accounts']} accounts"
        )


@router.post("/background")
async def sync_accounts_background(
    background_tasks: BackgroundTasks,
    sync_req: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger account synchronization in background."""
    
    async def run_sync():
        provider = get_bank_provider()
        if sync_req.account_id:
            account = db.query(Account).filter(
                Account.id == sync_req.account_id,
                Account.user_id == current_user.id
            ).first()
            if account:
                await sync_account_balances(db, provider, account.id)
                await sync_account_transactions(db, provider, account.id)
        else:
            await sync_all_user_accounts(db, provider, current_user.id)
    
    background_tasks.add_task(run_sync)
    
    return {"message": "Sync started in background"}
