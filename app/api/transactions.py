"""Transactions API endpoints."""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Transaction, Account
from app.schemas import TransactionResponse, AccountBalance
from app.api.auth import get_current_user
from app.services.balance_service import calculate_balance_at_date, get_net_balance
from app.services.categorization_service import get_transaction_categories

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/", response_model=List[TransactionResponse])
def list_transactions(
    account_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List transactions with optional filters."""
    query = db.query(Transaction).join(Account).filter(
        Account.user_id == current_user.id
    )
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    if date_from:
        query = query.filter(Transaction.booking_date >= date_from)
    
    if date_to:
        query = query.filter(Transaction.booking_date <= date_to)
    
    if status:
        query = query.filter(Transaction.status == status)
    
    query = query.order_by(Transaction.booking_date.desc())
    query = query.limit(limit).offset(offset)
    
    transactions = query.all()
    
    # Add categories to each transaction
    result = []
    for tx in transactions:
        categories = get_transaction_categories(db, tx.id)
        tx_dict = {
            "id": tx.id,
            "account_id": tx.account_id,
            "booking_date": tx.booking_date,
            "value_date": tx.value_date,
            "amount": tx.amount,
            "currency": tx.currency,
            "description": tx.description,
            "counterparty": tx.counterparty,
            "status": tx.status,
            "categories": [cat.name for cat in categories]
        }
        result.append(TransactionResponse(**tx_dict))
    
    return result


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific transaction."""
    transaction = db.query(Transaction).join(Account).filter(
        Transaction.id == transaction_id,
        Account.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    categories = get_transaction_categories(db, transaction.id)
    
    return TransactionResponse(
        id=transaction.id,
        account_id=transaction.account_id,
        booking_date=transaction.booking_date,
        value_date=transaction.value_date,
        amount=transaction.amount,
        currency=transaction.currency,
        description=transaction.description,
        counterparty=transaction.counterparty,
        status=transaction.status,
        categories=[cat.name for cat in categories]
    )


@router.get("/balances/current", response_model=List[AccountBalance])
def get_current_balances(
    as_of_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current balances for all accounts."""
    if not as_of_date:
        as_of_date = datetime.utcnow()
    
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    
    balances = []
    for account in accounts:
        balance = calculate_balance_at_date(db, account.id, as_of_date)
        if balance is not None:
            balances.append(AccountBalance(
                account_id=account.id,
                balance=balance,
                currency=account.currency,
                as_of_date=as_of_date
            ))
    
    return balances


@router.get("/balances/net")
def get_total_balance(
    as_of_date: Optional[datetime] = Query(None),
    currency: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get net balance across all accounts."""
    if not as_of_date:
        as_of_date = datetime.utcnow()
    
    balances = get_net_balance(db, current_user.id, as_of_date, currency)
    
    return {
        "as_of_date": as_of_date.isoformat(),
        "balances_by_currency": balances,
        "total": sum(balances.values()) if len(balances) == 1 else None
    }
