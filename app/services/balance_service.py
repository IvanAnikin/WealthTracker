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


def detect_and_mark_internal_transfers(db: Session, user_id: str) -> int:
    """
    Detect internal transfers (transactions between user's own accounts) and mark them.
    
    Enhanced logic to detect:
    1. Exact matching pairs (same amount, opposite sign, same/nearby dates)
    2. Revolut top-ups via card (Raiffeisen card payment → Revolut topup)
    3. Transfers containing user's name in counterparty
    4. Description patterns: "Topup", "Top-up", "Platba kartou" to Revolut
    
    Returns:
        Number of transactions updated
    """
    from datetime import timedelta
    
    # Get all user accounts
    user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    account_ids = {acc.id for acc in user_accounts}
    
    # Get all transactions for user accounts
    user_transactions = db.query(Transaction).filter(
        Transaction.account_id.in_(account_ids)
    ).order_by(Transaction.booking_date).all()
    
    updated_count = 0
    processed_pairs = set()
    
    # Patterns that indicate internal transfers
    internal_patterns = [
        'anikin', 'ivan', 'sergejev',  # User's name variations
        'topup', 'top-up', 'top up',  # Revolut topups
    ]
    
    revolut_account_ids = {acc.id for acc in user_accounts if acc.name and 'revolut' in acc.name.lower()}
    raiffeisen_account_ids = {acc.id for acc in user_accounts if acc.name and 'raiffeisen' in acc.name.lower()}
    
    for tx in user_transactions:
        if tx.id in processed_pairs:
            continue
        
        is_internal = False
        matching_tx = None
        
        # Pattern 1: Check if description/counterparty contains user's name
        description_lower = (tx.description or '').lower()
        counterparty_lower = (tx.counterparty or '').lower()
        
        if any(pattern in description_lower or pattern in counterparty_lower for pattern in internal_patterns):
            # If it's a transfer with user's own name, it's internal
            if 'anikin' in description_lower or 'anikin' in counterparty_lower:
                is_internal = True
        
        # Pattern 2: Revolut topups (check if it's a topup transaction)
        if tx.account_id in revolut_account_ids and tx.amount > 0:
            if 'topup' in description_lower or 'top-up' in description_lower or 'top up' in description_lower:
                # Look for matching card payment in Raiffeisen within 7 days before
                date_start = tx.booking_date - timedelta(days=7)
                date_end = tx.booking_date + timedelta(days=1)
                
                matching_tx = db.query(Transaction).filter(
                    Transaction.account_id.in_(raiffeisen_account_ids),
                    Transaction.amount == -tx.amount,  # Same amount but negative
                    Transaction.booking_date >= date_start,
                    Transaction.booking_date <= date_end,
                    Transaction.is_internal_transfer == False
                ).first()
                
                if matching_tx:
                    # Check if the Raiffeisen transaction mentions Revolut
                    raif_desc = (matching_tx.description or '').lower()
                    raif_counter = (matching_tx.counterparty or '').lower()
                    if 'revolut' in raif_desc or 'revolut' in raif_counter:
                        is_internal = True
        
        # Pattern 3: Card payments to Revolut from Raiffeisen
        if tx.account_id in raiffeisen_account_ids and tx.amount < 0:
            if 'revolut' in description_lower or 'revolut' in counterparty_lower:
                # This is a card payment to Revolut
                is_internal = True
                
                # Try to find matching topup at Revolut
                date_start = tx.booking_date
                date_end = tx.booking_date + timedelta(days=7)
                
                matching_tx = db.query(Transaction).filter(
                    Transaction.account_id.in_(revolut_account_ids),
                    Transaction.amount == -tx.amount,  # Opposite amount
                    Transaction.booking_date >= date_start,
                    Transaction.booking_date <= date_end,
                    Transaction.is_internal_transfer == False
                ).first()
        
        # Pattern 4: Standard matching pairs (same amount, opposite sign, within 3 days)
        if not is_internal and not matching_tx:
            date_start = tx.booking_date - timedelta(days=3)
            date_end = tx.booking_date + timedelta(days=3)
            
            matching_tx = db.query(Transaction).filter(
                Transaction.account_id.in_(account_ids),
                Transaction.account_id != tx.account_id,
                Transaction.amount == -tx.amount,  # Opposite amount
                Transaction.booking_date >= date_start,
                Transaction.booking_date <= date_end,
                Transaction.currency == tx.currency,
                Transaction.is_internal_transfer == False
            ).first()
            
            if matching_tx:
                is_internal = True
        
        # Update transactions if internal transfer detected
        if is_internal:
            if not tx.is_internal_transfer:
                tx.is_internal_transfer = True
                updated_count += 1
            processed_pairs.add(tx.id)
            
            if matching_tx and not matching_tx.is_internal_transfer:
                matching_tx.is_internal_transfer = True
                updated_count += 1
                processed_pairs.add(matching_tx.id)
        else:
            # Unmark if previously marked but no longer matches
            if tx.is_internal_transfer:
                tx.is_internal_transfer = False
                updated_count += 1
    
    db.commit()
    return updated_count
