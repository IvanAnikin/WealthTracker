"""Reporting service for cashflow and category analysis."""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func, extract, case
from sqlalchemy.orm import Session
from app.models import Transaction, Account, Category, TransactionCategory


def get_monthly_cashflow(
    db: Session,
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[str] = None,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False
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
    
    # Build query
    query = db.query(
        extract('year', Transaction.booking_date).label('year'),
        extract('month', Transaction.booking_date).label('month'),
        func.sum(
            case(
                (Transaction.amount > 0, Transaction.amount),
                else_=0
            )
        ).label('income'),
        func.sum(
            case(
                (Transaction.amount < 0, Transaction.amount),
                else_=0
            )
        ).label('expenses')
    ).join(
        Account
    ).filter(
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
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    query = query.group_by('year', 'month').order_by('year', 'month')
    
    results = query.all()
    
    cashflow_data = []
    for row in results:
        income = float(row.income or 0)
        expenses = float(row.expenses or 0)
        cashflow_data.append({
            'month': f"{int(row.year)}-{int(row.month):02d}",
            'income': income,
            'expenses': abs(expenses),
            'net': income + expenses  # expenses are negative
        })
    
    return cashflow_data


def get_category_breakdown(
    db: Session,
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[str] = None,
    exclude_investment: bool = False,
    exclude_internal_transfers: bool = False
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
    
    # Build query
    query = db.query(
        Category.id,
        Category.name,
        Category.color,
        Category.icon,
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('transaction_count')
    ).join(
        TransactionCategory, Category.id == TransactionCategory.category_id
    ).join(
        Transaction, TransactionCategory.transaction_id == Transaction.id
    ).join(
        Account, Transaction.account_id == Account.id
    ).filter(
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
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    query = query.group_by(
        Category.id, Category.name, Category.color, Category.icon
    ).order_by(func.abs(func.sum(Transaction.amount)).desc())
    
    results = query.all()
    
    breakdown_data = []
    for row in results:
        breakdown_data.append({
            'category_id': row.id,
            'category_name': row.name,
            'color': row.color,
            'icon': row.icon,
            'amount': float(row.total_amount or 0),
            'transaction_count': int(row.transaction_count or 0)
        })
    
    return breakdown_data


def get_spending_trends(
    db: Session,
    user_id: str,
    category_id: Optional[str] = None,
    months: int = 6
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
    exclude_internal_transfers: bool = False
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
    
    query = db.query(Transaction).join(Account).filter(
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
    
    total_transactions = query.count()
    
    income_query = query.filter(Transaction.amount > 0)
    total_income = db.query(func.sum(Transaction.amount)).select_from(income_query.subquery()).scalar() or 0
    income_count = income_query.count()
    
    expense_query = query.filter(Transaction.amount < 0)
    total_expenses = db.query(func.sum(Transaction.amount)).select_from(expense_query.subquery()).scalar() or 0
    expense_count = expense_query.count()
    
    return {
        'total_transactions': total_transactions,
        'income_count': income_count,
        'expense_count': expense_count,
        'total_income': float(total_income),
        'total_expenses': float(abs(total_expenses)),
        'net': float(total_income + total_expenses)
    }

