"""Categories API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Category, Transaction, Account
from app.schemas import CategoryCreate, CategoryResponse, RuleCreate, RuleResponse
from app.api.auth import get_current_user
from app.services.categorization_service import (
    categorize_transaction,
    auto_categorize_transactions,
    create_default_categories
)
from app.models import CategorizationRule

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's categories."""
    categories = db.query(Category).filter(
        Category.user_id == current_user.id
    ).order_by(Category.name).all()
    
    return categories


@router.post("/", response_model=CategoryResponse)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new category."""
    # Validate parent category if provided
    if category_data.parent_id:
        parent = db.query(Category).filter(
            Category.id == category_data.parent_id,
            Category.user_id == current_user.id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")
    
    category = Category(
        user_id=current_user.id,
        name=category_data.name,
        parent_id=category_data.parent_id,
        color=category_data.color,
        icon=category_data.icon
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str,
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a category."""
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category.name = category_data.name
    category.parent_id = category_data.parent_id
    category.color = category_data.color
    category.icon = category_data.icon
    
    db.commit()
    db.refresh(category)
    
    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a category."""
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    db.delete(category)
    db.commit()
    
    return {"message": "Category deleted successfully"}


@router.post("/transactions/{transaction_id}/categorize")
def assign_category(
    transaction_id: str,
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually assign a category to a transaction."""
    # Verify transaction belongs to user
    transaction = db.query(Transaction).join(Account).filter(
        Transaction.id == transaction_id,
        Account.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Verify category belongs to user
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    success = categorize_transaction(db, transaction_id, category_id, is_manual=True)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to categorize transaction")
    
    return {"message": "Transaction categorized successfully"}


@router.post("/auto-categorize")
def auto_categorize(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-categorize all uncategorized transactions."""
    result = auto_categorize_transactions(db, current_user.id)
    return result


@router.get("/rules", response_model=List[RuleResponse])
def list_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List categorization rules."""
    rules = db.query(CategorizationRule).filter(
        CategorizationRule.user_id == current_user.id
    ).order_by(CategorizationRule.priority.desc()).all()
    
    return rules


@router.post("/rules", response_model=RuleResponse)
def create_rule(
    rule_data: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new categorization rule."""
    # Verify category exists
    category = db.query(Category).filter(
        Category.id == rule_data.category_id,
        Category.user_id == current_user.id
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    rule = CategorizationRule(
        user_id=current_user.id,
        pattern=rule_data.pattern,
        field=rule_data.field,
        category_id=rule_data.category_id,
        priority=rule_data.priority,
        is_regex=rule_data.is_regex
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a categorization rule."""
    rule = db.query(CategorizationRule).filter(
        CategorizationRule.id == rule_id,
        CategorizationRule.user_id == current_user.id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    
    return {"message": "Rule deleted successfully"}
