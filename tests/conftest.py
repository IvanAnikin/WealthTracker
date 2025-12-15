"""Test configuration and fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models import User, Account, Transaction
from datetime import datetime, timedelta


@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        id="test-user-1",
        email="test@example.com",
        password_hash="hashed_password"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def test_account(test_db, test_user):
    """Create a test account."""
    account = Account(
        id="test-account-1",
        user_id=test_user.id,
        institution_id="TEST_BANK",
        requisition_id="test-req-1",
        currency="CZK",
        name="Test Account",
        initial_balance_amount=1000.0,
        initial_balance_date=datetime.utcnow() - timedelta(days=30)
    )
    test_db.add(account)
    test_db.commit()
    return account


@pytest.fixture
def test_transactions(test_db, test_account):
    """Create test transactions."""
    transactions = []
    base_date = datetime.utcnow() - timedelta(days=20)
    
    for i in range(10):
        tx = Transaction(
            id=f"tx-{i}",
            account_id=test_account.id,
            booking_date=base_date + timedelta(days=i*2),
            amount=(-1)**(i) * (i+1) * 100,  # Alternating +/- amounts
            currency="CZK",
            description=f"Transaction {i}",
            status="booked",
            hash=f"hash-{i}"
        )
        transactions.append(tx)
        test_db.add(tx)
    
    test_db.commit()
    return transactions
