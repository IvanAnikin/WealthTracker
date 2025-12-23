"""Tests for balance calculation service."""
import pytest
from datetime import datetime, timedelta
from app.services.balance_service import calculate_balance_at_date, get_net_balance


def test_balance_calculation_with_initial_balance(test_db, test_account, test_transactions):
    """Test balance calculation with initial balance and transactions."""
    # Calculate balance at a specific date
    calculation_date = datetime.utcnow() - timedelta(days=10)
    
    balance = calculate_balance_at_date(test_db, test_account.id, calculation_date)
    
    # Should include initial balance plus relevant transactions
    assert balance is not None
    assert isinstance(balance, float)
    
    # Verify it's different from initial balance (transactions should be included)
    assert balance != test_account.initial_balance_amount


def test_balance_calculation_no_account(test_db):
    """Test balance calculation with non-existent account."""
    balance = calculate_balance_at_date(test_db, "non-existent", datetime.utcnow())
    assert balance is None


def test_balance_calculation_before_initial_date(test_db, test_account):
    """Test balance calculation before initial balance date."""
    # Date before initial balance date
    early_date = test_account.initial_balance_date - timedelta(days=5)
    
    balance = calculate_balance_at_date(test_db, test_account.id, early_date)
    
    # Should return only initial balance (no transactions before initial date)
    assert balance == test_account.initial_balance_amount


def test_net_balance_calculation(test_db, test_user, test_account, test_transactions):
    """Test net balance calculation across accounts."""
    calculation_date = datetime.utcnow()
    
    balances = get_net_balance(test_db, test_user.id, calculation_date)
    
    assert isinstance(balances, dict)
    assert "CZK" in balances
    assert isinstance(balances["CZK"], float)


def test_balance_excludes_pending_transactions(test_db, test_account):
    """Test that pending transactions are excluded by default."""
    from app.models import Transaction
    
    # Add a pending transaction
    pending_tx = Transaction(
        id="pending-1",
        account_id=test_account.id,
        booking_date=datetime.utcnow(),
        amount=500.0,
        currency="CZK",
        status="pending",
        hash="pending-hash-1"
    )
    test_db.add(pending_tx)
    test_db.commit()
    
    # Calculate balance (should exclude pending)
    balance_without_pending = calculate_balance_at_date(
        test_db, test_account.id, datetime.utcnow(), include_pending=False
    )
    
    # Calculate balance (should include pending)
    balance_with_pending = calculate_balance_at_date(
        test_db, test_account.id, datetime.utcnow(), include_pending=True
    )
    
    # Balances should differ by the pending amount
    assert balance_with_pending == balance_without_pending + 500.0
