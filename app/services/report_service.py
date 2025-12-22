"""Reporting service for cashflow and category analysis."""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func, extract, case
from sqlalchemy.orm import Session
from app.models import Transaction, Account, Category, TransactionCategory


def _rate_map_for_target(currencies, target_currency):
    """Preload FX rates for a set of currencies to the target."""
    from app.services.currency_service import get_rate_map

    target = (target_currency or 'USD').upper()
    return get_rate_map(currencies, target), target


def _exclude_internal_query(query):
    """Apply additional filters to drop FX conversions and Revolut wallet moves when excluding internal transfers."""
    exclusion_patterns = [
        "%exchanged to %",
        "%revolut bank uab%",
        "%revolut digital assets%",
        "%transfer to revolut digital assets%",
        "%transfer to my account%",
        "%konverze%",
    ]
    for pat in exclusion_patterns:
        query = query.filter(~Transaction.description.ilike(pat))
    return query


def get_monthly_cashflow(
    db: Session,
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[str] = None,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False,
    currency: Optional[str] = None
) -> List[dict]:
    """
    Get monthly cashflow report (income vs expenses).
    
    Args:
        db: Database session
        user_id: User ID
        start_date: Start date for report
        end_date: End date for report
        account_id: Optional account filter
        exclude_investment: Exclude investment accounts
        exclude_internal_transfers: Exclude internal transfers
    
    Returns:
        List of monthly cashflow data
    """
    # Default to last 12 months
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=365)
    
    # Aggregate by month and currency, then convert sums once per currency
    income_case = case((Transaction.amount >= 0, Transaction.amount), else_=0)
    expense_case = case((Transaction.amount < 0, Transaction.amount), else_=0)

    query = db.query(
        extract('year', Transaction.booking_date).label('year'),
        extract('month', Transaction.booking_date).label('month'),
        Account.currency.label('currency'),
        func.sum(income_case).label('income_sum'),
        func.sum(expense_case).label('expense_sum')
    ).join(Account).filter(
        Account.user_id == user_id,
        Transaction.status == 'booked',
        Transaction.booking_date >= start_date,
        Transaction.booking_date <= end_date
    )

    # Apply filters
    if exclude_investment:
        query = query.filter(Account.account_purpose != 'investment')
    if exclude_internal_transfers:
        query = query.filter(Transaction.is_internal_transfer == False)
        query = _exclude_internal_query(query)
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    query = query.group_by('year', 'month', Account.currency)

    results = query.all()

    rate_map, target = _rate_map_for_target((r.currency for r in results), currency)

    buckets = {}
    for row in results:
        month_key = f"{int(row.year)}-{int(row.month):02d}"
        cur = (row.currency or 'USD').upper()
        rate = rate_map.get(cur, 1.0)
        income_converted = float(row.income_sum or 0) * rate
        expense_converted = abs(float(row.expense_sum or 0)) * rate
        b = buckets.setdefault(month_key, {'income': 0.0, 'expenses': 0.0})
        b['income'] += income_converted
        b['expenses'] += expense_converted

    cashflow_data = []
    for m in sorted(buckets.keys()):
        income = buckets[m]['income']
        expenses = buckets[m]['expenses']
        cashflow_data.append({
            'month': m,
            'income': round(income, 2),
            'expenses': round(expenses, 2),
            'net': round(income - expenses, 2)
        })
    
    return cashflow_data


def get_category_breakdown(
    db: Session,
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[str] = None,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False,
    currency: Optional[str] = None
) -> List[dict]:
    """
    Get spending breakdown by category.
    
    Args:
        db: Database session
        user_id: User ID
        start_date: Start date for report
        end_date: End date for report
        account_id: Optional account filter
        exclude_investment: Exclude investment accounts
        exclude_internal_transfers: Exclude internal transfers
    
    Returns:
        List of category breakdown data
    """
    # Default to last 30 days
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Aggregate by category and currency, convert sums once per currency
    query = db.query(
        Category.id.label('category_id'),
        Category.name,
        Category.color,
        Category.icon,
        Account.currency.label('currency'),
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('tx_count')
    ).join(TransactionCategory, TransactionCategory.category_id == Category.id).\
        join(Transaction, TransactionCategory.transaction_id == Transaction.id).\
        join(Account, Transaction.account_id == Account.id).\
        filter(
            Account.user_id == user_id,
            Transaction.status == 'booked',
            Transaction.booking_date >= start_date,
            Transaction.booking_date <= end_date
        )

    # Apply filters
    if exclude_investment:
        query = query.filter(Account.account_purpose != 'investment')
    if exclude_internal_transfers:
        query = query.filter(Transaction.is_internal_transfer == False)
        query = _exclude_internal_query(query)
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    query = query.group_by(Category.id, Category.name, Category.color, Category.icon, Account.currency)

    results = query.all()

    rate_map, target = _rate_map_for_target((r.currency for r in results), currency)

    buckets = {}
    counts = {}
    meta = {}
    for row in results:
        cur = (row.currency or 'USD').upper()
        rate = rate_map.get(cur, 1.0)
        amt_conv = float(row.total_amount or 0) * rate
        buckets[row.category_id] = buckets.get(row.category_id, 0.0) + amt_conv
        counts[row.category_id] = counts.get(row.category_id, 0) + int(row.tx_count or 0)
        meta[row.category_id] = {'name': row.name, 'color': row.color, 'icon': row.icon}

    breakdown_data = []
    for cid, total in sorted(buckets.items(), key=lambda kv: abs(kv[1]), reverse=True):
        info = meta[cid]
        breakdown_data.append({
            'category_id': cid,
            'category_name': info['name'],
            'color': info['color'],
            'icon': info['icon'],
            'amount': round(total, 2),
            'transaction_count': counts[cid]
        })
    
    return breakdown_data


def get_spending_trends(
    db: Session,
    user_id: str,
    category_id: Optional[str] = None,
    months: int = 6,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False
) -> List[dict]:
    """
    Get spending trends over time.
    
    Args:
        db: Database session
        user_id: User ID
        category_id: Optional category filter
        months: Number of months to analyze
    
    Returns:
        List of monthly spending data
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)
    
    query = db.query(
        extract('year', Transaction.booking_date).label('year'),
        extract('month', Transaction.booking_date).label('month'),
        func.sum(func.abs(Transaction.amount)).label('total_spending')
    ).join(
        Account
    ).filter(
        Account.user_id == user_id,
        Transaction.status == 'booked',
        Transaction.amount < 0,  # Only expenses
        Transaction.booking_date >= start_date,
        Transaction.booking_date <= end_date
    )
    
    if category_id:
        query = query.join(TransactionCategory).filter(
            TransactionCategory.category_id == category_id
        )
    
    # Apply filters
    if exclude_investment:
        query = query.filter(Account.account_purpose != 'investment')
    if exclude_internal_transfers:
        query = query.filter(Transaction.is_internal_transfer == False)
        query = _exclude_internal_query(query)

    query = query.group_by('year', 'month').order_by('year', 'month')
    
    results = query.all()
    
    trends_data = []
    for row in results:
        trends_data.append({
            'month': f"{int(row.year)}-{int(row.month):02d}",
            'spending': float(row.total_spending or 0)
        })
    
    return trends_data


def get_account_summary(
    db: Session,
    user_id: str,
    as_of_date: Optional[datetime] = None
) -> List[dict]:
    """
    Get summary of all accounts with current balances.
    
    Args:
        db: Database session
        user_id: User ID
        as_of_date: Date for balance calculation (default: now)
    
    Returns:
        List of account summaries
    """
    if not as_of_date:
        as_of_date = datetime.utcnow()
    
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    
    from app.services.balance_service import calculate_balance_at_date
    
    summary = []
    for account in accounts:
        balance = calculate_balance_at_date(db, account.id, as_of_date)
        summary.append({
            'account_id': account.id,
            'account_name': account.name or f"Account {account.id[:8]}",
            'institution_id': account.institution_id,
            'iban': account.iban,
            'currency': account.currency,
            'balance': balance,
            'last_synced': account.last_synced_at.isoformat() if account.last_synced_at else None
        })
    
    return summary


def get_transaction_statistics(
    db: Session,
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False,
    currency: Optional[str] = None
) -> dict:
    """
    Get overall transaction statistics.
    
    Args:
        db: Database session
        user_id: User ID
        start_date: Start date
        end_date: End date
        exclude_investment: Exclude investment accounts
        exclude_internal_transfers: Exclude internal transfers
    
    Returns:
        Dictionary with statistics
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    income_case = case((Transaction.amount >= 0, Transaction.amount), else_=0)
    expense_case = case((Transaction.amount < 0, Transaction.amount), else_=0)
    income_count_case = case((Transaction.amount >= 0, 1), else_=0)
    expense_count_case = case((Transaction.amount < 0, 1), else_=0)

    query = db.query(
        Account.currency.label('currency'),
        func.sum(income_case).label('income_sum'),
        func.sum(expense_case).label('expense_sum'),
        func.sum(income_count_case).label('income_count'),
        func.sum(expense_count_case).label('expense_count'),
        func.count(Transaction.id).label('total_count')
    ).join(Account).filter(
        Account.user_id == user_id,
        Transaction.status == 'booked',
        Transaction.booking_date >= start_date,
        Transaction.booking_date <= end_date
    )
    
    # Apply filters
    if exclude_investment:
        query = query.filter(Account.account_purpose != 'investment')
    if exclude_internal_transfers:
        query = query.filter(Transaction.is_internal_transfer == False)
        query = _exclude_internal_query(query)
    
    query = query.group_by(Account.currency)

    results = query.all()
    target = (currency or 'USD').upper()
    rate_map, target = _rate_map_for_target((r.currency for r in results), currency)

    income = 0.0
    expenses = 0.0
    income_count = 0
    expense_count = 0
    total_transactions = 0

    for row in results:
        cur = (row.currency or 'USD').upper()
        rate = rate_map.get(cur, 1.0)
        income += float(row.income_sum or 0) * rate
        expenses += abs(float(row.expense_sum or 0)) * rate
        income_count += int(row.income_count or 0)
        expense_count += int(row.expense_count or 0)
        total_transactions += int(row.total_count or 0)

    return {
        'total_transactions': total_transactions,
        'income_count': income_count,
        'expense_count': expense_count,
        'total_income': round(income, 2),
        'total_expenses': round(expenses, 2),
        'net': round(income - expenses, 2),
        'currency': target
    }

