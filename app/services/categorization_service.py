"""Transaction categorization service."""
import re
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Transaction, Category, CategorizationRule, TransactionCategory


def apply_categorization_rules(
    db: Session,
    transaction: Transaction,
    user_id: str
) -> Optional[str]:
    """
    Apply categorization rules to a transaction.
    
    Args:
        db: Database session
        transaction: Transaction to categorize
        user_id: User ID (owner of rules)
    
    Returns:
        Category ID if a rule matched, None otherwise
    """
    # Get all rules for user, ordered by priority (highest first)
    rules = db.query(CategorizationRule).filter(
        CategorizationRule.user_id == user_id
    ).order_by(CategorizationRule.priority.desc()).all()
    
    for rule in rules:
        # Determine which field to check
        if rule.field == "description":
            field_value = transaction.description or ""
        elif rule.field == "counterparty":
            field_value = transaction.counterparty or ""
        else:
            continue
        
        # Check if pattern matches
        matched = False
        if rule.is_regex:
            try:
                matched = bool(re.search(rule.pattern, field_value, re.IGNORECASE))
            except re.error:
                # Invalid regex, skip
                continue
        else:
            # Simple substring match
            matched = rule.pattern.lower() in field_value.lower()
        
        if matched:
            return rule.category_id
    
    return None


def categorize_transaction(
    db: Session,
    transaction_id: str,
    category_id: str,
    is_manual: bool = True,
    confidence: Optional[float] = None
) -> bool:
    """
    Assign a category to a transaction.
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        category_id: Category ID
        is_manual: Whether this is a manual categorization
        confidence: Confidence score (for automatic categorization)
    
    Returns:
        True if successful, False otherwise
    """
    # Check if transaction exists
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        return False
    
    # Check if category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return False
    
    # Remove existing categorization
    db.query(TransactionCategory).filter(
        TransactionCategory.transaction_id == transaction_id
    ).delete()
    
    # Add new categorization
    tx_category = TransactionCategory(
        transaction_id=transaction_id,
        category_id=category_id,
        is_manual=is_manual,
        confidence=confidence
    )
    db.add(tx_category)
    db.commit()
    
    return True


def auto_categorize_transactions(
    db: Session,
    user_id: str,
    transaction_ids: Optional[List[str]] = None
) -> dict:
    """
    Auto-categorize transactions using rules.
    
    Args:
        db: Database session
        user_id: User ID
        transaction_ids: Optional list of specific transaction IDs to categorize
    
    Returns:
        Dictionary with categorization statistics
    """
    # Get transactions to categorize
    query = db.query(Transaction).join(
        Transaction.account
    ).filter(
        Transaction.account.has(user_id=user_id)
    )
    
    if transaction_ids:
        query = query.filter(Transaction.id.in_(transaction_ids))
    else:
        # Only categorize uncategorized transactions
        query = query.outerjoin(TransactionCategory).filter(
            TransactionCategory.transaction_id.is_(None)
        )
    
    transactions = query.all()
    
    categorized_count = 0
    for transaction in transactions:
        category_id = apply_categorization_rules(db, transaction, user_id)
        if category_id:
            categorize_transaction(
                db,
                transaction.id,
                category_id,
                is_manual=False,
                confidence=0.8
            )
            categorized_count += 1
    
    return {
        "total_processed": len(transactions),
        "categorized": categorized_count,
        "uncategorized": len(transactions) - categorized_count
    }


def get_transaction_categories(
    db: Session,
    transaction_id: str
) -> List[Category]:
    """
    Get categories assigned to a transaction.
    
    Args:
        db: Database session
        transaction_id: Transaction ID
    
    Returns:
        List of Category objects
    """
    tx_categories = db.query(TransactionCategory).filter(
        TransactionCategory.transaction_id == transaction_id
    ).all()
    
    categories = []
    for tx_cat in tx_categories:
        category = db.query(Category).filter(Category.id == tx_cat.category_id).first()
        if category:
            categories.append(category)
    
    return categories


def create_default_categories(db: Session, user_id: str) -> List[Category]:
    """
    Create default categories for a new user.
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        List of created categories
    """
    default_categories = [
        {"name": "Income", "color": "#4CAF50", "icon": "💰"},
        {"name": "Salary", "color": "#66BB6A", "icon": "💼", "parent": "Income"},
        {"name": "Investments", "color": "#81C784", "icon": "📈", "parent": "Income"},
        {"name": "Food & Dining", "color": "#FF9800", "icon": "🍔"},
        {"name": "Groceries", "color": "#FFB74D", "icon": "🛒", "parent": "Food & Dining"},
        {"name": "Restaurants", "color": "#FFCC80", "icon": "🍽️", "parent": "Food & Dining"},
        {"name": "Transportation", "color": "#2196F3", "icon": "🚗"},
        {"name": "Shopping", "color": "#E91E63", "icon": "🛍️"},
        {"name": "Entertainment", "color": "#9C27B0", "icon": "🎬"},
        {"name": "Bills & Utilities", "color": "#795548", "icon": "📄"},
        {"name": "Healthcare", "color": "#F44336", "icon": "⚕️"},
        {"name": "Other", "color": "#9E9E9E", "icon": "📦"},
    ]
    
    categories_map = {}
    created_categories = []
    
    # First pass: create categories without parents
    for cat_data in default_categories:
        if "parent" not in cat_data:
            category = Category(
                user_id=user_id,
                name=cat_data["name"],
                color=cat_data.get("color"),
                icon=cat_data.get("icon")
            )
            db.add(category)
            db.flush()
            categories_map[cat_data["name"]] = category
            created_categories.append(category)
    
    # Second pass: create categories with parents
    for cat_data in default_categories:
        if "parent" in cat_data:
            parent_category = categories_map.get(cat_data["parent"])
            if parent_category:
                category = Category(
                    user_id=user_id,
                    name=cat_data["name"],
                    parent_id=parent_category.id,
                    color=cat_data.get("color"),
                    icon=cat_data.get("icon")
                )
                db.add(category)
                created_categories.append(category)
    
    db.commit()
    return created_categories
