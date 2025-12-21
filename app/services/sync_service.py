"""Transaction synchronization and deduplication service."""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Account, Transaction, BalanceSnapshot, Category, TransactionCategory
from app.services.bank_provider import BankProviderClient


def _auto_categorize_transaction(
    db: Session,
    transaction: Transaction,
    user_id: str
) -> bool:
    """
    Auto-categorize a transaction based on counterparty/description patterns.
    
    Returns:
        True if categorized, False otherwise
    """
    if not transaction.counterparty and not transaction.description:
        return False
    
    field_value = (transaction.counterparty or "") + " " + (transaction.description or "")
    field_value_lower = field_value.lower()
    
    # Define category patterns
    category_patterns = {
        "Groceries": ["albert", "lidl", "tesco", "kaufland", "penny", "billa", "rewe"],
        "Utilities": ["čez", "vodafone", "o2 czech", "telefonica", "electro", "water", "plyn"],
        "Transport": ["shell", "bp", "aral", "motoil", "fuel", "benzin", "Praha", "Prague", "autobus", "MHD", "ticket"],
        "Restaurants": ["lokál", "restaurant", "cafe", "coffee", "starbucks", "kfc", "mcdonalds", "pizza", "u fleků"],
        "Entertainment": ["cinema", "kinema", "netflix", "spotify", "hulu", "museum", "theater"],
        "Shopping": ["h&m", "zara", "primark", "decathlon", "alza", "mall"],
        "Healthcare": ["pharmacy", "lékárna", "dentist", "doctor", "zdravi"],
        "Subscriptions": ["netflix", "spotify", "apple", "microsoft", "adobe"],
        "Salary": ["salary", "plat", "mzda", "abc software", "income"],
        "Transfers": ["transfer", "sending", "převod"]
    }
    
    # Try to match patterns
    for category_name, patterns in category_patterns.items():
        for pattern in patterns:
            if pattern in field_value_lower:
                # Get or create category
                category = db.query(Category).filter(
                    Category.name == category_name,
                    Category.user_id == user_id
                ).first()
                
                if not category:
                    category = Category(
                        name=category_name,
                        user_id=user_id,
                        color="#3498db",
                        icon="📊"
                    )
                    db.add(category)
                    db.flush()
                
                # Create transaction-category link
                existing_link = db.query(TransactionCategory).filter(
                    TransactionCategory.transaction_id == transaction.id,
                    TransactionCategory.category_id == category.id
                ).first()
                
                if not existing_link:
                    tx_cat = TransactionCategory(
                        transaction_id=transaction.id,
                        category_id=category.id,
                        is_manual=False,
                        confidence=0.9
                    )
                    db.add(tx_cat)
                
                return True
    
    return False


def generate_transaction_hash(
    account_id: str,
    booking_date: datetime,
    amount: float,
    description: Optional[str],
    counterparty: Optional[str]
) -> str:
    """
    Generate a unique hash for a transaction.
    
    This is used as a fallback when external_id is not available.
    """
    data = f"{account_id}|{booking_date.isoformat()}|{amount}|{description or ''}|{counterparty or ''}"
    return hashlib.sha256(data.encode()).hexdigest()


async def sync_account_transactions(
    db: Session,
    provider: BankProviderClient,
    account_id: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> dict:
    """
    Sync transactions for a specific account.
    
    Args:
        db: Database session
        provider: Bank provider client
        account_id: Account ID
        date_from: Start date for fetching transactions
        date_to: End date for fetching transactions
    
    Returns:
        Dictionary with sync statistics
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {"error": "Account not found", "transactions_added": 0}
    
    # Default date range: last 90 days to today
    if not date_from:
        date_from = datetime.utcnow() - timedelta(days=90)
    if not date_to:
        date_to = datetime.utcnow()
    
    # Fetch transactions from provider
    try:
        data = await provider.get_transactions(account_id, date_from, date_to)
    except Exception as e:
        return {"error": str(e), "transactions_added": 0}
    
    transactions_data = data.get("transactions", {})
    booked_txs = transactions_data.get("booked", [])
    pending_txs = transactions_data.get("pending", [])
    
    transactions_added = 0
    
    # Process booked transactions
    for tx_data in booked_txs:
        transactions_added += _save_transaction(db, account, tx_data, "booked", account.user_id)
    
    # Process pending transactions
    for tx_data in pending_txs:
        transactions_added += _save_transaction(db, account, tx_data, "pending", account.user_id)
    
    # Update account sync timestamp
    account.last_synced_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "success",
        "transactions_added": transactions_added,
        "total_fetched": len(booked_txs) + len(pending_txs)
    }


def _save_transaction(
    db: Session,
    account: Account,
    tx_data: dict,
    status: str,
    user_id: str
) -> int:
    """
    Save a single transaction to database with deduplication.
    
    Returns:
        1 if transaction was added, 0 if it was a duplicate
    """
    # Extract transaction data
    external_id = tx_data.get("transactionId") or tx_data.get("internalTransactionId")
    
    # Parse dates
    booking_date_str = tx_data.get("bookingDate")
    value_date_str = tx_data.get("valueDate")
    
    try:
        booking_date = datetime.fromisoformat(booking_date_str) if booking_date_str else datetime.utcnow()
    except (ValueError, TypeError):
        booking_date = datetime.utcnow()
    
    try:
        value_date = datetime.fromisoformat(value_date_str) if value_date_str else None
    except (ValueError, TypeError):
        value_date = None
    
    # Parse amount
    amount_data = tx_data.get("transactionAmount", {})
    try:
        amount = float(amount_data.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0.0
    
    currency = amount_data.get("currency", account.currency)
    
    # Extract description and counterparty
    description = (
        tx_data.get("remittanceInformationUnstructured") or
        tx_data.get("remittanceInformationUnstructuredArray", [""])[0] or
        tx_data.get("additionalInformation") or
        ""
    )
    
    counterparty = (
        tx_data.get("creditorName") or
        tx_data.get("debtorName") or
        tx_data.get("creditorAccount", {}).get("iban") or
        tx_data.get("debtorAccount", {}).get("iban") or
        ""
    )
    
    # Generate hash
    tx_hash = generate_transaction_hash(
        account.id,
        booking_date,
        amount,
        description,
        counterparty
    )
    
    # Check for existing transaction
    existing = db.query(Transaction).filter(
        Transaction.account_id == account.id,
        Transaction.hash == tx_hash
    ).first()
    
    if existing:
        # Update if status changed (e.g., pending -> booked)
        if existing.status != status:
            existing.status = status
            db.commit()
        return 0
    
    # Create new transaction
    transaction = Transaction(
        account_id=account.id,
        external_id=external_id,
        booking_date=booking_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        description=description,
        counterparty=counterparty,
        status=status,
        raw_payload=tx_data,
        hash=tx_hash
    )
    
    try:
        db.add(transaction)
        db.flush()
        
        # Auto-categorize the transaction
        _auto_categorize_transaction(db, transaction, user_id)
        
        db.commit()
        return 1
    except IntegrityError:
        db.rollback()
        return 0


async def sync_account_balances(
    db: Session,
    provider: BankProviderClient,
    account_id: str
) -> dict:
    """
    Sync balance snapshots for an account.
    
    Args:
        db: Database session
        provider: Bank provider client
        account_id: Account ID
    
    Returns:
        Dictionary with sync status
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {"error": "Account not found"}
    
    try:
        data = await provider.get_balances(account_id)
    except Exception as e:
        return {"error": str(e)}
    
    balances = data.get("balances", [])
    
    for balance_data in balances:
        balance_amount_data = balance_data.get("balanceAmount", {})
        amount = float(balance_amount_data.get("amount", 0))
        balance_type = balance_data.get("balanceType", "")
        reference_date_str = balance_data.get("referenceDate")
        
        if reference_date_str:
            try:
                reference_date = datetime.fromisoformat(reference_date_str)
            except (ValueError, TypeError):
                reference_date = datetime.utcnow()
        else:
            reference_date = datetime.utcnow()
        
        # Update initial balance if not set
        if not account.initial_balance_amount and balance_type in ["expected", "interimAvailable"]:
            account.initial_balance_amount = amount
            account.initial_balance_date = reference_date
        
        # Save balance snapshot
        snapshot = BalanceSnapshot(
            account_id=account_id,
            as_of=reference_date,
            booked=amount,
            available=amount
        )
        db.add(snapshot)
    
    db.commit()
    return {"status": "success", "balances_saved": len(balances)}


async def sync_all_user_accounts(
    db: Session,
    provider: BankProviderClient,
    user_id: str
) -> dict:
    """
    Sync all accounts for a user.
    
    Args:
        db: Database session
        provider: Bank provider client
        user_id: User ID
    
    Returns:
        Dictionary with sync statistics
    """
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    
    total_transactions = 0
    accounts_synced = 0
    errors = []
    
    for account in accounts:
        # Sync balances
        balance_result = await sync_account_balances(db, provider, account.id)
        if "error" in balance_result:
            errors.append(f"Account {account.id}: {balance_result['error']}")
            continue
        
        # Sync transactions
        tx_result = await sync_account_transactions(db, provider, account.id)
        if "error" in tx_result:
            errors.append(f"Account {account.id}: {tx_result['error']}")
            continue
        
        total_transactions += tx_result.get("transactions_added", 0)
        accounts_synced += 1
    
    return {
        "status": "success" if not errors else "partial",
        "accounts_synced": accounts_synced,
        "total_accounts": len(accounts),
        "transactions_added": total_transactions,
        "errors": errors
    }
