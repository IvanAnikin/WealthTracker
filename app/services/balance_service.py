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
    target_currency: Optional[str] = None
) -> tuple[dict[str, float], Optional[float], Optional[str]]:
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
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    balances_by_currency = {}
    
    for account in accounts:
        balance = calculate_balance_at_date(db, account.id, as_of_date)
        if balance is not None:
            currency = account.currency
            balances_by_currency[currency] = balances_by_currency.get(currency, 0.0) + balance

    converted_total = None
    target = (target_currency or '').upper() or None
    if target:
        from app.services.currency_service import get_rate_map

        rate_map = get_rate_map(balances_by_currency.keys(), target)
        converted_total = sum((balances_by_currency[cur] or 0.0) * rate_map.get(cur.upper(), 1.0)
                               for cur in balances_by_currency)

    return balances_by_currency, converted_total, target


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
    
    # Bulk mark obvious FX/internal wallet conversions up front (single-table scan)
    simple_internal_patterns = [
        'exchanged to ',
        'revolut bank uab',
        'revolut digital assets',
        'transfer to revolut digital assets',
        'transfer to my account',
        'konverze'
    ]
    updated_count = 0

    base_query = db.query(Transaction).join(Account).filter(Account.user_id == user_id)
    conversions = base_query.filter(
        Transaction.is_internal_transfer == False,
        Transaction.description.ilike('%exchanged to %')
    ).all()
    for tx in conversions:
        # Keep cash withdrawals as expenses
        desc_lower = (tx.description or '').lower()
        if 'cash withdrawal' in desc_lower:
            continue
        tx.is_internal_transfer = True
        updated_count += 1

    other_simple = base_query.filter(
        Transaction.is_internal_transfer == False,
        (
            Transaction.description.ilike('%revolut bank uab%') |
            Transaction.description.ilike('%revolut digital assets%') |
            Transaction.description.ilike('%transfer to revolut digital assets%') |
            Transaction.description.ilike('%transfer to my account%') |
            Transaction.description.ilike('%konverze%')
        )
    ).all()
    for tx in other_simple:
        desc_lower = (tx.description or '').lower()
        if 'cash withdrawal' in desc_lower:
            continue
        tx.is_internal_transfer = True
        updated_count += 1

    # Get all user accounts
    user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    account_ids = {acc.id for acc in user_accounts}
    
    # Get all transactions for user accounts
    user_transactions = db.query(Transaction).filter(
        Transaction.account_id.in_(account_ids)
    ).order_by(Transaction.booking_date).all()
    
    processed_pairs = set()
    
    # Patterns that indicate internal transfers or investment/wallet moves
    internal_patterns = [
        'anikin', 'ivan', 'sergejev',  # User's name variations
        'topup', 'top-up', 'top up',   # Revolut topups
        'revolut',
        'revolut bank uab',
        'revolut digital assets',
        'konverze',                    # FX conversion lines
        'transfer to my account',
        'transfer to revolut',
        'exchanged to ',               # FX conversions wording
        'xtb'
    ]

    account_identifiers = set()
    for acc in user_accounts:
        if acc.iban:
            account_identifiers.add(acc.iban.replace(' ', '').lower())
        if acc.name:
            account_identifiers.add(acc.name.lower())
    
    revolut_account_ids = {acc.id for acc in user_accounts if acc.name and 'revolut' in acc.name.lower()}
    raiffeisen_account_ids = {acc.id for acc in user_accounts if acc.name and 'raiffeisen' in acc.name.lower()}
    kb_account_ids = {acc.id for acc in user_accounts if acc.name and ('komer' in acc.name.lower() or 'kb ' in acc.name.lower())}
    
    for tx in user_transactions:
        if tx.id in processed_pairs:
            continue
        
        is_internal = False
        matching_tx = None
        
        # Pattern 1: Check if description/counterparty contains user's name or own account identifiers
        description_lower = (tx.description or '').lower()
        counterparty_lower = (tx.counterparty or '').lower()
        
        if any(pattern in description_lower or pattern in counterparty_lower for pattern in internal_patterns):
            is_internal = True

        if not is_internal and any(identifier in description_lower or identifier in counterparty_lower for identifier in account_identifiers):
            is_internal = True
        
        # Explicit FX conversions like "Exchanged to EUR/USD" should be internal unless they are cash withdrawals
        if not is_internal and 'exchanged to ' in description_lower:
            if 'cash withdrawal' not in description_lower:
                is_internal = True

        # Cash withdrawals should stay as expenses; do not mark internal
        if description_lower.startswith('cash withdrawal'):
            is_internal = False

        # Pattern 2: Revolut topups (check if it's a topup transaction)
        if tx.account_id in revolut_account_ids and tx.amount > 0:
            if 'topup' in description_lower or 'top-up' in description_lower or 'top up' in description_lower:
                # Look for matching card payment in Raiffeisen within 7 days before
                # Increase window to catch cross-month matches and KB card payments
                date_start = tx.booking_date - timedelta(days=30)
                date_end = tx.booking_date + timedelta(days=3)
                
                matching_tx = db.query(Transaction).filter(
                    Transaction.account_id.in_(raiffeisen_account_ids.union(kb_account_ids)),
                    Transaction.amount == -tx.amount,  # Same amount but negative
                    Transaction.booking_date >= date_start,
                    Transaction.booking_date <= date_end,
                    Transaction.is_internal_transfer == False
                ).first()
                
                if matching_tx:
                    # Check if the Raiffeisen transaction mentions Revolut
                    raif_desc = (matching_tx.description or '').lower()
                    raif_counter = (matching_tx.counterparty or '').lower()
                    # Prefer Revolut mention, but accept exact amount match as internal
                    if 'revolut' in raif_desc or 'revolut' in raif_counter or True:
                        is_internal = True
        
        # Pattern 3: Card payments to Revolut from Raiffeisen
        if (tx.account_id in raiffeisen_account_ids or tx.account_id in kb_account_ids) and tx.amount < 0:
            if 'revolut' in description_lower or 'revolut' in counterparty_lower:
                # This is a card payment to Revolut
                is_internal = True
                
                # Try to find matching topup at Revolut
                date_start = tx.booking_date - timedelta(days=1)
                date_end = tx.booking_date + timedelta(days=30)
                
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
