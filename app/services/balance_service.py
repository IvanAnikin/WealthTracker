"""Balance calculation service."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Account, Transaction


def calculate_balance_at_date(
    db: Session,
    account_id: str,
    as_of_date: datetime,
    include_pending: bool = False
) -> Optional[float]:
    """
    Calculate account balance at a specific date.
    
    Formula:
        balance(D) = initial_balance_amount
                   + SUM(transaction.amount)
                     WHERE transaction.booking_date > initial_balance_date
                       AND transaction.booking_date <= D
                       AND transaction.status = 'booked'
    
    Args:
        db: Database session
        account_id: Account ID
        as_of_date: Date to calculate balance for
        include_pending: Whether to include pending transactions
    
    Returns:
        Balance amount or None if account not found
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return None
    
    # Start with initial balance
    balance = account.initial_balance_amount or 0.0
    initial_date = account.initial_balance_date
    
    # Build query for transactions
    if initial_date:
        # If initial balance date is set, only include transactions after that date
        query = db.query(Transaction).filter(
            Transaction.account_id == account_id,
            Transaction.booking_date > initial_date,
            Transaction.booking_date <= as_of_date
        )
    else:
        # For CSV imports without initial balance, include all transactions
        query = db.query(Transaction).filter(
            Transaction.account_id == account_id,
            Transaction.booking_date <= as_of_date
        )
    
    # Filter by status
    if not include_pending:
        query = query.filter(Transaction.status == "booked")
    
    # Sum all transaction amounts
    transactions = query.all()
    for tx in transactions:
        balance += tx.amount
    
    return balance


def calculate_balances_for_accounts(
    db: Session,
    account_ids: list[str],
    as_of_date: datetime,
    include_pending: bool = False
) -> dict[str, float]:
    """
    Calculate balances for multiple accounts.
    
    Args:
        db: Database session
        account_ids: List of account IDs
        as_of_date: Date to calculate balance for
        include_pending: Whether to include pending transactions
    
    Returns:
        Dictionary mapping account_id to balance
    """
    balances = {}
    for account_id in account_ids:
        balance = calculate_balance_at_date(db, account_id, as_of_date, include_pending)
        if balance is not None:
            balances[account_id] = balance
    return balances


def get_net_balance(
    db: Session,
    user_id: str,
    as_of_date: datetime,
    currency_filter: Optional[str] = None
) -> dict[str, float]:
    """
    Get total net balance across all user accounts.
    
    Args:
        db: Database session
        user_id: User ID
        as_of_date: Date to calculate balance for
        currency_filter: Optional currency filter
    
    Returns:
        Dictionary with balances per currency
    """
    query = db.query(Account).filter(Account.user_id == user_id)
    if currency_filter:
        query = query.filter(Account.currency == currency_filter)
    
    accounts = query.all()
    balances_by_currency = {}
    
    for account in accounts:
        balance = calculate_balance_at_date(db, account.id, as_of_date)
        if balance is not None:
            currency = account.currency
            balances_by_currency[currency] = balances_by_currency.get(currency, 0.0) + balance
    
    return balances_by_currency
