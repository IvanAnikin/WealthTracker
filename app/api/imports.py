"""CSV import API endpoints."""
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Account, Institution, Transaction, ImportBatch, ImportedTransaction, Category
from app.api.auth import get_current_user
from app.services.csv_parsers import CSVParserFactory
from app.services.sync_service import _auto_categorize_transaction
import hashlib

router = APIRouter(prefix="/imports", tags=["CSV Import"])


def generate_transaction_hash(
    account_id: str,
    booking_date: datetime,
    amount: float,
    description: Optional[str],
    counterparty: Optional[str]
) -> str:
    """Generate unique hash for deduplication."""
    data = f"{account_id}|{booking_date.isoformat()}|{amount}|{description or ''}|{counterparty or ''}"
    return hashlib.sha256(data.encode()).hexdigest()


@router.post("/accounts")
async def create_manual_account(
    account_type: str = Form(...),  # "Raiffeisen main", "Revolut CZK", etc.
    account_name: Optional[str] = Form(None),
    currency: str = Form("CZK"),
    iban: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a manual CSV import account."""
    
    # Get or create "Manual" institution
    institution = db.query(Institution).filter(Institution.id == "MANUAL_CSV").first()
    if not institution:
        institution = Institution(
            id="MANUAL_CSV",
            name="Manual CSV Import",
            country="CZ",
            logo_url="📄"
        )
        db.add(institution)
        db.flush()
    
    # Create account
    account_id = f"manual_csv_{uuid.uuid4()}"
    account = Account(
        id=account_id,
        user_id=current_user.id,
        institution_id="MANUAL_CSV",
        requisition_id=None,  # No requisition for manual imports
        name=account_name or account_type,
        account_type=account_type,
        currency=currency,
        iban=iban,
        source_type="csv_manual"
    )
    db.add(account)
    db.commit()
    
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "currency": account.currency,
        "source_type": account.source_type,
        "message": "Account created successfully. Ready for CSV import."
    }


@router.post("/accounts/{account_id}/preview")
async def preview_import(
    account_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Preview CSV import without saving."""
    
    # Verify account ownership
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Read and parse CSV - try multiple encodings
    file_bytes = await file.read()
    
    # Try common encodings
    content = None
    for encoding in ['utf-8', 'windows-1250', 'iso-8859-1', 'cp1252']:
        try:
            content = file_bytes.decode(encoding)
            break
        except:
            continue
    
    if not content:
        raise HTTPException(status_code=400, detail="Could not decode CSV file. Unsupported encoding.")
    
    # Detect bank
    bank_name = CSVParserFactory.detect_bank(content)
    if not bank_name:
        raise HTTPException(status_code=400, detail="Could not detect bank format")
    
    # Parse transactions
    csv_transactions = CSVParserFactory.parse(content)
    if not csv_transactions:
        raise HTTPException(status_code=400, detail="No transactions found in CSV")
    
    # Check for duplicates
    duplicates = 0
    for csv_tx in csv_transactions:
        tx_hash = generate_transaction_hash(
            account_id,
            csv_tx.booking_date,
            float(csv_tx.amount),
            csv_tx.description,
            csv_tx.counterparty
        )
        existing = db.query(Transaction).filter(
            Transaction.account_id == account_id,
            Transaction.hash == tx_hash
        ).first()
        if existing:
            duplicates += 1
    
    return {
        "bank_name": bank_name,
        "filename": file.filename,
        "total_transactions": len(csv_transactions),
        "estimated_new": len(csv_transactions) - duplicates,
        "estimated_duplicates": duplicates,
        "sample_transactions": [
            {
                "booking_date": csv_tx.booking_date.isoformat(),
                "amount": float(csv_tx.amount),
                "currency": csv_tx.currency,
                "description": csv_tx.description,
                "counterparty": csv_tx.counterparty,
            }
            for csv_tx in csv_transactions[:5]
        ]
    }


@router.post("/accounts/{account_id}/import")
async def import_csv(
    account_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import transactions from CSV file."""
    
    # Verify account ownership
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Read and parse CSV
    try:
        content = (await file.read()).decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    # Detect bank
    bank_name = CSVParserFactory.detect_bank(content) or "Unknown"
    
    # Parse transactions
    csv_transactions = CSVParserFactory.parse(content)
    if not csv_transactions:
        raise HTTPException(status_code=400, detail="No transactions found in CSV")
    
    # Create import batch
    batch = ImportBatch(
        id=str(uuid.uuid4()),
        account_id=account_id,
        user_id=current_user.id,
        filename=file.filename or "import.csv",
        bank_name=bank_name,
        transaction_count=len(csv_transactions),
        status="processing"
    )
    db.add(batch)
    db.flush()
    
    # Import transactions
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    errors = []
    
    for row_idx, csv_tx in enumerate(csv_transactions, 1):
        try:
            # Generate hash for deduplication
            tx_hash = generate_transaction_hash(
                account_id,
                csv_tx.booking_date,
                float(csv_tx.amount),
                csv_tx.description,
                csv_tx.counterparty
            )
            
            # Check for duplicate
            existing = db.query(Transaction).filter(
                Transaction.account_id == account_id,
                Transaction.hash == tx_hash
            ).first()
            
            if existing:
                duplicate_count += 1
                imported_tx = ImportedTransaction(
                    id=str(uuid.uuid4()),
                    batch_id=batch.id,
                    transaction_id=existing.id,
                    original_id=csv_tx.original_id,
                    row_number=row_idx,
                    is_duplicate=True
                )
                db.add(imported_tx)
                continue
            
            # Create transaction
            transaction = Transaction(
                id=str(uuid.uuid4()),
                account_id=account_id,
                external_id=csv_tx.original_id,
                booking_date=csv_tx.booking_date,
                value_date=csv_tx.value_date,
                amount=float(csv_tx.amount),
                currency=csv_tx.currency,
                description=csv_tx.description,
                counterparty=csv_tx.counterparty,
                status="booked",
                hash=tx_hash,
                raw_payload=csv_tx.metadata
            )
            db.add(transaction)
            db.flush()
            
            # Auto-categorize
            _auto_categorize_transaction(db, transaction, current_user.id)
            
            # Track imported transaction
            imported_tx = ImportedTransaction(
                id=str(uuid.uuid4()),
                batch_id=batch.id,
                transaction_id=transaction.id,
                original_id=csv_tx.original_id,
                row_number=row_idx,
                is_duplicate=False
            )
            db.add(imported_tx)
            
            imported_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"Row {row_idx}: {str(e)}")
            print(f"Error importing transaction at row {row_idx}: {e}")
            continue
    
    # Update batch status
    batch.imported_count = imported_count
    batch.duplicate_count = duplicate_count
    batch.error_count = error_count
    batch.status = "completed" if error_count == 0 else "partial"
    batch.completed_at = datetime.utcnow()
    if errors:
        batch.error_details = "\n".join(errors[:50])  # Store first 50 errors
    
    db.commit()
    
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "imported": imported_count,
        "duplicates": duplicate_count,
        "errors": error_count,
        "message": f"Import completed: {imported_count} new, {duplicate_count} duplicates, {error_count} errors"
    }


@router.get("/accounts/{account_id}/history")
async def import_history(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import history for an account."""
    
    # Verify account ownership
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    batches = db.query(ImportBatch).filter(
        ImportBatch.account_id == account_id
    ).order_by(ImportBatch.created_at.desc()).all()
    
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "bank_name": b.bank_name,
            "status": b.status,
            "imported": b.imported_count,
            "duplicates": b.duplicate_count,
            "errors": b.error_count,
            "created_at": b.created_at.isoformat(),
            "completed_at": b.completed_at.isoformat() if b.completed_at else None
        }
        for b in batches
    ]


@router.delete("/accounts/{account_id}/imports/{batch_id}")
async def delete_import_batch(
    account_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an import batch and its transactions."""
    
    # Verify account ownership
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.account_id == account_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get all imported transactions
    imported_txs = db.query(ImportedTransaction).filter(
        ImportedTransaction.batch_id == batch_id
    ).all()
    
    # Delete transactions
    for imp_tx in imported_txs:
        db.query(Transaction).filter(Transaction.id == imp_tx.transaction_id).delete()
    
    # Delete batch
    db.delete(batch)
    db.commit()
    
    return {"message": f"Deleted {len(imported_txs)} transactions from batch"}
