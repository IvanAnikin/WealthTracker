"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# User Schemas
class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    email: str
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Institution Schemas
class InstitutionResponse(BaseModel):
    """Schema for institution response."""
    id: str
    name: str
    country: str
    logo_url: Optional[str] = None
    
    class Config:
        from_attributes = True


# Requisition Schemas
class RequisitionCreate(BaseModel):
    """Schema for creating a requisition."""
    institution_id: str
    redirect_url: str


class RequisitionResponse(BaseModel):
    """Schema for requisition response."""
    id: str
    institution_id: str
    status: str
    created_at: datetime
    linked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Account Schemas
class AccountResponse(BaseModel):
    """Schema for account response."""
    id: str
    institution_id: str
    iban: Optional[str] = None
    currency: str
    name: Optional[str] = None
    account_type: Optional[str] = None
    owner_name: Optional[str] = None
    initial_balance_amount: Optional[float] = None
    initial_balance_date: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AccountBalance(BaseModel):
    """Schema for account balance."""
    account_id: str
    balance: float
    currency: str
    as_of_date: datetime


# Transaction Schemas
class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: str
    account_id: str
    booking_date: datetime
    value_date: Optional[datetime] = None
    amount: float
    currency: str
    description: Optional[str] = None
    counterparty: Optional[str] = None
    status: str
    categories: List[str] = []
    
    class Config:
        from_attributes = True


class TransactionFilter(BaseModel):
    """Schema for filtering transactions."""
    account_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: Optional[str] = None
    category_id: Optional[str] = None


# Category Schemas
class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str
    parent_id: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: str
    name: str
    parent_id: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    
    class Config:
        from_attributes = True


# Categorization Rule Schemas
class RuleCreate(BaseModel):
    """Schema for creating a categorization rule."""
    pattern: str
    field: str  # description or counterparty
    category_id: str
    priority: int = 0
    is_regex: bool = False


class RuleResponse(BaseModel):
    """Schema for rule response."""
    id: str
    pattern: str
    field: str
    category_id: str
    priority: int
    is_regex: bool
    
    class Config:
        from_attributes = True


# Report Schemas
class CashflowReport(BaseModel):
    """Schema for cashflow report."""
    month: str
    income: float
    expenses: float
    net: float


class CategoryBreakdown(BaseModel):
    """Schema for category breakdown."""
    category_id: str
    category_name: str
    amount: float
    transaction_count: int


# Sync Schemas
class SyncRequest(BaseModel):
    """Schema for sync request."""
    account_id: Optional[str] = None
    force: bool = False


class SyncResponse(BaseModel):
    """Schema for sync response."""
    status: str
    accounts_synced: int
    transactions_added: int
    message: str
