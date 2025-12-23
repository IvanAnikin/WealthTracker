"""Export API endpoints."""
import csv
import io
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Transaction, Account
from app.api.auth import get_current_user
from app.services.report_service import get_monthly_cashflow, get_category_breakdown
from app.services.categorization_service import get_transaction_categories

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/transactions.csv")
def export_transactions_csv(
    account_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export transactions to CSV."""
    query = db.query(Transaction).join(Account).filter(
        Account.user_id == current_user.id
    )
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    if date_from:
        query = query.filter(Transaction.booking_date >= date_from)
    
    if date_to:
        query = query.filter(Transaction.booking_date <= date_to)
    
    query = query.order_by(Transaction.booking_date.desc())
    transactions = query.all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date',
        'Account ID',
        'Amount',
        'Currency',
        'Description',
        'Counterparty',
        'Status',
        'Categories'
    ])
    
    # Write data
    for tx in transactions:
        categories = get_transaction_categories(db, tx.id)
        category_names = ', '.join([cat.name for cat in categories])
        
        writer.writerow([
            tx.booking_date.date().isoformat(),
            tx.account_id,
            tx.amount,
            tx.currency,
            tx.description or '',
            tx.counterparty or '',
            tx.status,
            category_names
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"}
    )


@router.get("/cashflow.csv")
def export_cashflow_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export cashflow report to CSV."""
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=365)
    
    data = get_monthly_cashflow(db, current_user.id, start_date, end_date)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Month', 'Income', 'Expenses', 'Net'])
    
    # Write data
    for row in data:
        writer.writerow([
            row['month'],
            row['income'],
            row['expenses'],
            row['net']
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cashflow.csv"}
    )


@router.get("/categories.csv")
def export_categories_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export category breakdown to CSV."""
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    data = get_category_breakdown(db, current_user.id, start_date, end_date)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Category', 'Amount', 'Transaction Count'])
    
    # Write data
    for row in data:
        writer.writerow([
            row['category_name'],
            row['amount'],
            row['transaction_count']
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=categories.csv"}
    )
