"""Tests for categorization rules."""
import pytest
from app.models import Category, Transaction, CategorizationRule
from app.services.categorization_service import apply_categorization_rules, create_default_categories
from datetime import datetime


def test_create_default_categories(test_db, test_user):
    """Test creation of default categories for new user."""
    categories = create_default_categories(test_db, test_user.id)
    
    assert len(categories) > 0
    
    # Check that common categories were created
    category_names = [cat.name for cat in categories]
    assert "Income" in category_names
    assert "Food & Dining" in category_names
    assert "Transportation" in category_names


def test_simple_pattern_matching(test_db, test_user, test_account):
    """Test simple substring pattern matching."""
    # Create a category
    category = Category(
        user_id=test_user.id,
        name="Groceries"
    )
    test_db.add(category)
    test_db.flush()
    
    # Create a rule
    rule = CategorizationRule(
        user_id=test_user.id,
        pattern="supermarket",
        field="description",
        category_id=category.id,
        priority=10,
        is_regex=False
    )
    test_db.add(rule)
    test_db.commit()
    
    # Create a transaction
    transaction = Transaction(
        id="tx-grocery-1",
        account_id=test_account.id,
        booking_date=datetime.utcnow(),
        amount=-50.0,
        currency="CZK",
        description="Payment at SuperMarket",
        status="booked",
        hash="hash-grocery-1"
    )
    test_db.add(transaction)
    test_db.commit()
    
    # Apply rules
    matched_category_id = apply_categorization_rules(test_db, transaction, test_user.id)
    
    assert matched_category_id == category.id


def test_regex_pattern_matching(test_db, test_user, test_account):
    """Test regex pattern matching."""
    # Create a category
    category = Category(
        user_id=test_user.id,
        name="Online Shopping"
    )
    test_db.add(category)
    test_db.flush()
    
    # Create a regex rule
    rule = CategorizationRule(
        user_id=test_user.id,
        pattern=r"(amazon|ebay|aliexpress)",
        field="counterparty",
        category_id=category.id,
        priority=10,
        is_regex=True
    )
    test_db.add(rule)
    test_db.commit()
    
    # Create transactions
    tx1 = Transaction(
        id="tx-shop-1",
        account_id=test_account.id,
        booking_date=datetime.utcnow(),
        amount=-100.0,
        currency="CZK",
        counterparty="Amazon.com",
        status="booked",
        hash="hash-shop-1"
    )
    test_db.add(tx1)
    test_db.commit()
    
    # Apply rules
    matched_category_id = apply_categorization_rules(test_db, tx1, test_user.id)
    
    assert matched_category_id == category.id


def test_rule_priority(test_db, test_user, test_account):
    """Test that higher priority rules are matched first."""
    # Create two categories
    cat1 = Category(user_id=test_user.id, name="General")
    cat2 = Category(user_id=test_user.id, name="Specific")
    test_db.add_all([cat1, cat2])
    test_db.flush()
    
    # Create two rules with different priorities
    rule1 = CategorizationRule(
        user_id=test_user.id,
        pattern="payment",
        field="description",
        category_id=cat1.id,
        priority=5,
        is_regex=False
    )
    rule2 = CategorizationRule(
        user_id=test_user.id,
        pattern="payment",
        field="description",
        category_id=cat2.id,
        priority=10,  # Higher priority
        is_regex=False
    )
    test_db.add_all([rule1, rule2])
    test_db.commit()
    
    # Create a transaction
    tx = Transaction(
        id="tx-priority-1",
        account_id=test_account.id,
        booking_date=datetime.utcnow(),
        amount=-50.0,
        currency="CZK",
        description="payment test",
        status="booked",
        hash="hash-priority-1"
    )
    test_db.add(tx)
    test_db.commit()
    
    # Apply rules - should match higher priority rule
    matched_category_id = apply_categorization_rules(test_db, tx, test_user.id)
    
    assert matched_category_id == cat2.id  # Higher priority


def test_no_match_returns_none(test_db, test_user, test_account):
    """Test that no match returns None."""
    # Create a transaction with no matching rule
    tx = Transaction(
        id="tx-nomatch-1",
        account_id=test_account.id,
        booking_date=datetime.utcnow(),
        amount=-50.0,
        currency="CZK",
        description="unique transaction description",
        status="booked",
        hash="hash-nomatch-1"
    )
    test_db.add(tx)
    test_db.commit()
    
    # Apply rules
    matched_category_id = apply_categorization_rules(test_db, tx, test_user.id)
    
    assert matched_category_id is None
