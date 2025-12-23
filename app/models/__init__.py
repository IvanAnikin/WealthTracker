"""Database models for the application."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Float, 
    Boolean, Integer, Index, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    requisitions = relationship("Requisition", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    rules = relationship("CategorizationRule", back_populates="user", cascade="all, delete-orphan")


class Institution(Base):
    """Bank institution model."""
    __tablename__ = "institutions"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    country = Column(String(2), nullable=False, index=True)
    logo_url = Column(String(512), nullable=True)
    
    # Relationships
    requisitions = relationship("Requisition", back_populates="institution")
    accounts = relationship("Account", back_populates="institution")


class Requisition(Base):
    """Consent/requisition model for Open Banking connections."""
    __tablename__ = "requisitions"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    institution_id = Column(String(255), ForeignKey("institutions.id"), nullable=False)
    status = Column(String(50), nullable=False, default="created")  # created, linked, expired, revoked
    reference = Column(String(255), nullable=True)
    agreement_id = Column(String(255), nullable=True)
    redirect_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    linked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="requisitions")
    institution = relationship("Institution", back_populates="requisitions")
    accounts = relationship("Account", back_populates="requisition")


class Account(Base):
    """Bank account model."""
    __tablename__ = "accounts"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    institution_id = Column(String(255), ForeignKey("institutions.id"), nullable=False)
    requisition_id = Column(String(255), ForeignKey("requisitions.id"), nullable=False)
    iban = Column(String(34), nullable=True)
    currency = Column(String(3), nullable=False, default="EUR")
    name = Column(String(255), nullable=True)
    account_type = Column(String(50), nullable=True)
    owner_name = Column(String(255), nullable=True)
    initial_balance_amount = Column(Float, nullable=True)
    initial_balance_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    institution = relationship("Institution", back_populates="accounts")
    requisition = relationship("Requisition", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    balance_snapshots = relationship("BalanceSnapshot", back_populates="account", cascade="all, delete-orphan")


class BalanceSnapshot(Base):
    """Balance snapshot at a specific point in time."""
    __tablename__ = "balance_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(255), ForeignKey("accounts.id"), nullable=False, index=True)
    as_of = Column(DateTime, nullable=False, index=True)
    booked = Column(Float, nullable=False)
    available = Column(Float, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="balance_snapshots")
    
    __table_args__ = (
        Index('ix_balance_snapshots_account_date', 'account_id', 'as_of'),
    )


class Transaction(Base):
    """Transaction model."""
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(255), ForeignKey("accounts.id"), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    booking_date = Column(DateTime, nullable=False, index=True)
    value_date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    description = Column(Text, nullable=True)
    counterparty = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="booked")  # booked, pending
    raw_payload = Column(JSON, nullable=True)
    hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="transactions")
    transaction_categories = relationship("TransactionCategory", back_populates="transaction", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_transactions_account_booking', 'account_id', 'booking_date'),
        UniqueConstraint('account_id', 'hash', name='uq_account_transaction_hash'),
    )


class Category(Base):
    """Category model for transaction categorization."""
    __tablename__ = "categories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    color = Column(String(7), nullable=True)
    icon = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="categories")
    parent = relationship("Category", remote_side=[id], backref="children")
    transaction_categories = relationship("TransactionCategory", back_populates="category")
    rules = relationship("CategorizationRule", back_populates="category")


class TransactionCategory(Base):
    """Many-to-many relationship between transactions and categories."""
    __tablename__ = "transaction_categories"
    
    transaction_id = Column(String(36), ForeignKey("transactions.id"), primary_key=True)
    category_id = Column(String(36), ForeignKey("categories.id"), primary_key=True)
    is_manual = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="transaction_categories")
    category = relationship("Category", back_populates="transaction_categories")


class CategorizationRule(Base):
    """Rule-based categorization model."""
    __tablename__ = "categorization_rules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    pattern = Column(String(512), nullable=False)
    field = Column(String(50), nullable=False)  # description, counterparty
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    is_regex = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="rules")
    category = relationship("Category", back_populates="rules")
    
    __table_args__ = (
        Index('ix_rules_user_priority', 'user_id', 'priority'),
    )
