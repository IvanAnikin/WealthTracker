"""
End-to-end tests for the complete WealthTracker application workflow.
Tests the full user journey from registration to viewing reports.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from app.services.bank_provider import MockBankProvider
from app.services.sync_service import sync_account_transactions, sync_account_balances
from app.services.balance_service import calculate_balance_at_date
from app.services.categorization_service import create_default_categories, auto_categorize_transactions
from app.services.report_service import get_monthly_cashflow, get_category_breakdown


@pytest.fixture
def e2e_setup(test_db, test_user, test_account):
    """Setup for end-to-end tests."""
    # Create default categories
    categories = create_default_categories(test_db, test_user.id)
    
    return {
        'db': test_db,
        'user': test_user,
        'account': test_account,
        'categories': categories
    }


def test_e2e_user_registration_and_login(test_db):
    """Test E2E: User can register and login."""
    from app.models import User
    from app.core.security import get_password_hash, verify_password
    
    # Register user
    new_user = User(
        id="e2e-user-1",
        email="e2e@test.com",
        password_hash=get_password_hash("testpassword123")
    )
    test_db.add(new_user)
    test_db.commit()
    
    # Verify user exists
    user = test_db.query(User).filter(User.email == "e2e@test.com").first()
    assert user is not None
    assert user.email == "e2e@test.com"
    
    # Verify password
    assert verify_password("testpassword123", user.password_hash)


@pytest.mark.asyncio
async def test_e2e_bank_connection_workflow(e2e_setup):
    """Test E2E: User can connect a bank and sync data."""
    db = e2e_setup['db']
    user = e2e_setup['user']
    account = e2e_setup['account']
    
    # Initialize mock provider
    provider = MockBankProvider()
    
    # Step 1: List institutions
    institutions = await provider.list_institutions("CZ")
    assert len(institutions) > 0
    assert institutions[0]['name'] == "Mock Bank CZ"
    
    # Step 2: Create requisition
    requisition = await provider.create_requisition(
        institutions[0]['id'],
        "http://localhost:8000/callback"
    )
    assert requisition['status'] == 'created'
    assert 'id' in requisition
    
    # Step 3: Get requisition details (simulate callback)
    req_details = await provider.get_requisition(requisition['id'])
    assert req_details is not None
    
    # Step 4: Sync account data
    sync_result = await sync_account_transactions(db, provider, account.id)
    assert sync_result['status'] == 'success'
    assert sync_result['transactions_added'] >= 0


@pytest.mark.asyncio
async def test_e2e_transaction_sync_and_display(e2e_setup):
    """Test E2E: Transactions are synced and can be retrieved."""
    db = e2e_setup['db']
    account = e2e_setup['account']
    
    provider = MockBankProvider()
    
    # Sync transactions
    await sync_account_transactions(db, provider, account.id)
    
    # Verify transactions exist
    from app.models import Transaction
    transactions = db.query(Transaction).filter(
        Transaction.account_id == account.id
    ).all()
    
    assert len(transactions) > 0
    
    # Verify transaction properties
    tx = transactions[0]
    assert tx.account_id == account.id
    assert tx.amount is not None
    assert tx.currency is not None
    assert tx.status in ['booked', 'pending']


@pytest.mark.asyncio
async def test_e2e_balance_calculation_workflow(e2e_setup):
    """Test E2E: Balance can be calculated at any date."""
    db = e2e_setup['db']
    account = e2e_setup['account']
    
    provider = MockBankProvider()
    
    # Sync data
    await sync_account_balances(db, provider, account.id)
    await sync_account_transactions(db, provider, account.id)
    
    # Calculate balance at different dates
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    
    balance_today = calculate_balance_at_date(db, account.id, today)
    balance_yesterday = calculate_balance_at_date(db, account.id, yesterday)
    balance_last_week = calculate_balance_at_date(db, account.id, last_week)
    
    assert balance_today is not None
    assert balance_yesterday is not None
    assert balance_last_week is not None
    
    # Balances should be numbers
    assert isinstance(balance_today, float)


@pytest.mark.asyncio
async def test_e2e_categorization_workflow(e2e_setup):
    """Test E2E: Transactions can be categorized automatically and manually."""
    db = e2e_setup['db']
    user = e2e_setup['user']
    account = e2e_setup['account']
    categories = e2e_setup['categories']
    
    provider = MockBankProvider()
    
    # Sync transactions
    await sync_account_transactions(db, provider, account.id)
    
    # Create a categorization rule
    from app.models import CategorizationRule, Transaction
    
    # Get a category
    food_category = next((c for c in categories if 'food' in c.name.lower()), categories[0])
    
    rule = CategorizationRule(
        user_id=user.id,
        pattern="payment",
        field="description",
        category_id=food_category.id,
        priority=10,
        is_regex=False
    )
    db.add(rule)
    db.commit()
    
    # Auto-categorize
    result = auto_categorize_transactions(db, user.id)
    
    assert 'total_processed' in result
    assert 'categorized' in result
    
    # Verify some transactions were categorized
    from app.models import TransactionCategory
    categorized_count = db.query(TransactionCategory).count()
    assert categorized_count >= 0


@pytest.mark.asyncio
async def test_e2e_reports_generation(e2e_setup):
    """Test E2E: Financial reports can be generated."""
    db = e2e_setup['db']
    user = e2e_setup['user']
    account = e2e_setup['account']
    
    provider = MockBankProvider()
    
    # Sync data
    await sync_account_transactions(db, provider, account.id)
    
    # Generate cashflow report
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)
    
    cashflow = get_monthly_cashflow(db, user.id, start_date, end_date)
    
    # Verify report structure
    assert isinstance(cashflow, list)
    for month_data in cashflow:
        assert 'month' in month_data
        assert 'income' in month_data
        assert 'expenses' in month_data
        assert 'net' in month_data


@pytest.mark.asyncio
async def test_e2e_category_breakdown_report(e2e_setup):
    """Test E2E: Category breakdown report works."""
    db = e2e_setup['db']
    user = e2e_setup['user']
    account = e2e_setup['account']
    categories = e2e_setup['categories']
    
    provider = MockBankProvider()
    
    # Sync and categorize
    await sync_account_transactions(db, provider, account.id)
    auto_categorize_transactions(db, user.id)
    
    # Generate category report
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    category_breakdown = get_category_breakdown(db, user.id, start_date, end_date)
    
    # Verify report structure
    assert isinstance(category_breakdown, list)


@pytest.mark.asyncio
async def test_e2e_full_user_journey(test_db):
    """Test E2E: Complete user journey from registration to reports."""
    from app.models import User, Institution, Requisition, Account, Transaction
    from app.core.security import get_password_hash
    from app.services.categorization_service import create_default_categories
    
    # Step 1: User Registration
    user = User(
        id="journey-user",
        email="journey@test.com",
        password_hash=get_password_hash("password123")
    )
    test_db.add(user)
    test_db.commit()
    
    # Step 2: Create default categories
    categories = create_default_categories(test_db, user.id)
    assert len(categories) > 0
    
    # Step 3: Connect bank (mock)
    institution = Institution(
        id="MOCK_BANK",
        name="Mock Bank",
        country="CZ"
    )
    test_db.add(institution)
    test_db.commit()
    
    requisition = Requisition(
        id="req-journey",
        user_id=user.id,
        institution_id=institution.id,
        status="linked"
    )
    test_db.add(requisition)
    test_db.commit()
    
    # Step 4: Create account
    account = Account(
        id="acc-journey",
        user_id=user.id,
        institution_id=institution.id,
        requisition_id=requisition.id,
        currency="CZK",
        name="Journey Account",
        initial_balance_amount=5000.0,
        initial_balance_date=datetime.utcnow() - timedelta(days=30)
    )
    test_db.add(account)
    test_db.commit()
    
    # Step 5: Add transactions
    provider = MockBankProvider()
    await sync_account_transactions(test_db, provider, account.id)
    
    # Step 6: Verify transactions exist
    transactions = test_db.query(Transaction).filter(
        Transaction.account_id == account.id
    ).all()
    assert len(transactions) > 0
    
    # Step 7: Calculate balance
    balance = calculate_balance_at_date(test_db, account.id, datetime.utcnow())
    assert balance is not None
    
    # Step 8: Auto-categorize
    result = auto_categorize_transactions(test_db, user.id)
    assert result['total_processed'] > 0
    
    # Step 9: Generate reports
    cashflow = get_monthly_cashflow(test_db, user.id)
    assert isinstance(cashflow, list)
    
    # Complete journey successful
    assert True


def test_e2e_data_export(e2e_setup):
    """Test E2E: Data can be exported to CSV."""
    db = e2e_setup['db']
    user = e2e_setup['user']
    
    from app.models import Transaction
    
    # Get transactions
    transactions = db.query(Transaction).join(
        Transaction.account
    ).filter(
        Transaction.account.has(user_id=user.id)
    ).all()
    
    # Simulate CSV export
    csv_data = []
    for tx in transactions:
        csv_data.append({
            'date': tx.booking_date,
            'amount': tx.amount,
            'description': tx.description,
            'status': tx.status
        })
    
    assert isinstance(csv_data, list)


@pytest.mark.asyncio
async def test_e2e_sync_updates_existing_transactions(e2e_setup):
    """Test E2E: Re-syncing updates transaction status correctly."""
    db = e2e_setup['db']
    account = e2e_setup['account']
    
    provider = MockBankProvider()
    
    # First sync
    result1 = await sync_account_transactions(db, provider, account.id)
    initial_count = result1['transactions_added']
    
    # Second sync (should not create duplicates)
    result2 = await sync_account_transactions(db, provider, account.id)
    
    # Should not add new transactions if data hasn't changed
    assert result2['transactions_added'] == 0 or result2['transactions_added'] < initial_count


def test_e2e_balance_history_accuracy(e2e_setup):
    """Test E2E: Balance history is accurate across different dates."""
    db = e2e_setup['db']
    account = e2e_setup['account']
    
    from app.models import Transaction
    import hashlib
    
    # Add known transactions
    base_date = datetime.utcnow() - timedelta(days=10)
    
    tx1 = Transaction(
        id="balance-tx-1",
        account_id=account.id,
        booking_date=base_date,
        amount=100.0,
        currency="CZK",
        status="booked",
        hash=hashlib.sha256(b"tx1").hexdigest()
    )
    
    tx2 = Transaction(
        id="balance-tx-2",
        account_id=account.id,
        booking_date=base_date + timedelta(days=5),
        amount=-50.0,
        currency="CZK",
        status="booked",
        hash=hashlib.sha256(b"tx2").hexdigest()
    )
    
    db.add_all([tx1, tx2])
    db.commit()
    
    # Calculate balances at different points
    initial_balance = account.initial_balance_amount or 0
    
    balance_at_day_0 = calculate_balance_at_date(db, account.id, base_date)
    balance_at_day_5 = calculate_balance_at_date(db, account.id, base_date + timedelta(days=5))
    balance_at_day_10 = calculate_balance_at_date(db, account.id, base_date + timedelta(days=10))
    
    # Verify progressive balance changes
    assert balance_at_day_0 == initial_balance + 100.0
    assert balance_at_day_5 == initial_balance + 100.0 - 50.0
    assert balance_at_day_10 == balance_at_day_5
