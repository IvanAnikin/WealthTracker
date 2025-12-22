"""Reports API endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User
from app.schemas import CashflowReport, CategoryBreakdown
from app.api.auth import get_current_user
from app.services.report_service import (
    get_monthly_cashflow,
    get_category_breakdown,
    get_spending_trends,
    get_account_summary,
    get_transaction_statistics
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/cashflow", response_model=List[CashflowReport])
def cashflow_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    account_id: Optional[str] = Query(None),
    exclude_investment: bool = Query(False),
    exclude_internal_transfers: bool = Query(False),
    currency: Optional[str] = Query('USD'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly cashflow report."""
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=365)
    
    data = get_monthly_cashflow(
        db, current_user.id, start_date, end_date, account_id,
        exclude_investment=exclude_investment,
        exclude_internal_transfers=exclude_internal_transfers,
        currency=currency
    )
    return [CashflowReport(**item) for item in data]


@router.get("/categories", response_model=List[CategoryBreakdown])
def category_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    account_id: Optional[str] = Query(None),
    exclude_investment: bool = Query(False),
    exclude_internal_transfers: bool = Query(False),
    currency: Optional[str] = Query('USD'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get category breakdown report."""
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    data = get_category_breakdown(
        db, current_user.id, start_date, end_date, account_id,
        exclude_investment=exclude_investment,
        exclude_internal_transfers=exclude_internal_transfers,
        currency=currency
    )
    return [CategoryBreakdown(**item) for item in data]


@router.get("/trends")
def spending_trends(
    category_id: Optional[str] = Query(None),
    months: int = Query(6, ge=1, le=24),
    exclude_investment: bool = Query(False),
    exclude_internal_transfers: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get spending trends over time."""
    data = get_spending_trends(
        db, current_user.id, category_id, months,
        exclude_investment=exclude_investment,
        exclude_internal_transfers=exclude_internal_transfers
    )
    return {"trends": data}


@router.get("/accounts")
def accounts_summary(
    as_of_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get account summary with balances."""
    if not as_of_date:
        as_of_date = datetime.utcnow()
    
    data = get_account_summary(db, current_user.id, as_of_date)
    return {"accounts": data, "as_of_date": as_of_date.isoformat()}


@router.get("/statistics")
def transaction_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    exclude_investment: bool = Query(False),
    exclude_internal_transfers: bool = Query(False),
    currency: Optional[str] = Query('USD'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get transaction statistics."""
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    stats = get_transaction_statistics(
        db, current_user.id, start_date, end_date,
        exclude_investment=exclude_investment,
        exclude_internal_transfers=exclude_internal_transfers,
        currency=currency
    )
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        **stats
    }


@router.post("/detect-internal-transfers")
def detect_internal_transfers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Detect and mark internal transfers between user's accounts."""
    from app.services.balance_service import detect_and_mark_internal_transfers
    
    updated_count = detect_and_mark_internal_transfers(db, current_user.id)
    return {
        "success": True,
        "updated_count": updated_count,
        "message": f"Detected and marked {updated_count} internal transfer transactions"
    }
