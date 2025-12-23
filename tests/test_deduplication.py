"""Tests for transaction deduplication."""
import pytest
from datetime import datetime
from app.services.sync_service import generate_transaction_hash


def test_transaction_hash_generation():
    """Test that transaction hash is generated consistently."""
    account_id = "test-account"
    booking_date = datetime(2024, 1, 15)
    amount = -150.50
    description = "Payment to Amazon"
    counterparty = "Amazon.com"
    
    hash1 = generate_transaction_hash(account_id, booking_date, amount, description, counterparty)
    hash2 = generate_transaction_hash(account_id, booking_date, amount, description, counterparty)
    
    # Same inputs should produce same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64-character hex string


def test_transaction_hash_different_inputs():
    """Test that different inputs produce different hashes."""
    base_date = datetime(2024, 1, 15)
    
    hash1 = generate_transaction_hash("acc1", base_date, -100, "desc1", "party1")
    hash2 = generate_transaction_hash("acc1", base_date, -100, "desc2", "party1")
    hash3 = generate_transaction_hash("acc1", base_date, -101, "desc1", "party1")
    
    # Different inputs should produce different hashes
    assert hash1 != hash2
    assert hash1 != hash3
    assert hash2 != hash3


def test_transaction_hash_handles_none_values():
    """Test that hash generation handles None values."""
    account_id = "test-account"
    booking_date = datetime(2024, 1, 15)
    amount = -150.50
    
    # Should not raise an error with None description/counterparty
    hash1 = generate_transaction_hash(account_id, booking_date, amount, None, None)
    hash2 = generate_transaction_hash(account_id, booking_date, amount, "", "")
    
    # None and empty string should produce same hash (both treated as empty)
    assert hash1 == hash2
    assert len(hash1) == 64
