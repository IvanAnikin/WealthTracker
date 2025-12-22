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


@router.post("/detect-currencies")
async def detect_currencies(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Detect currencies in a Revolut CSV file."""
    
    # Read and parse CSV
    file_bytes = await file.read()
    
    content = None
    for encoding in ['utf-8', 'utf-8-sig', 'windows-1250', 'iso-8859-1', 'cp1252']:
        try:
            content = file_bytes.decode(encoding)
            break
        except Exception:
            continue
    
    if not content:
        raise HTTPException(status_code=400, detail="Failed to read file: Unsupported encoding")
    
    # Parse transactions
    csv_transactions = CSVParserFactory.parse(content)
    if not csv_transactions:
        raise HTTPException(status_code=400, detail="No transactions found in CSV")
    
    # Get unique currencies and count transactions per currency
    currency_counts = {}
    for tx in csv_transactions:
        currency = tx.currency
        currency_counts[currency] = currency_counts.get(currency, 0) + 1
    
    return {
        "currencies": sorted(currency_counts.keys()),
        "transaction_counts": currency_counts,
        "total_transactions": len(csv_transactions)
    }


@router.post("/accounts/{account_id}/import")
async def import_csv(
    account_id: str,
    file: UploadFile = File(...),
    selected_currencies: Optional[str] = Form(None),
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
    file_bytes = await file.read()

    content = None
    for encoding in ['utf-8', 'utf-8-sig', 'windows-1250', 'iso-8859-1', 'cp1252']:
        try:
            content = file_bytes.decode(encoding)
            break
        except Exception:
            continue

    if not content:
        raise HTTPException(status_code=400, detail="Failed to read file: Unsupported encoding")
    
    # Detect bank
    bank_name = CSVParserFactory.detect_bank(content) or "Unknown"
    
    # Parse transactions
    csv_transactions = CSVParserFactory.parse(content)
    if not csv_transactions:
        raise HTTPException(status_code=400, detail="No transactions found in CSV")
    
    # Parse selected currencies if provided
    import json
    currencies_to_import = None
    if selected_currencies:
        try:
            currencies_to_import = json.loads(selected_currencies)
        except:
            pass
    
    # Check if this is a Revolut multi-currency import (Current, Crypto, or Stock)
    is_revolut_multicurrency = (
        ("Revolut" in bank_name and ("Current" in bank_name or "Crypto" in bank_name or "Stock" in bank_name)) or 
        (account.account_type in ["Revolut Current", "Revolut crypto", "Revolut stock"])
    )
    
    if is_revolut_multicurrency:
        # Get unique currencies from transactions
        currencies_in_csv = set(tx.currency for tx in csv_transactions)
        
        # Filter by selected currencies if provided
        if currencies_to_import:
            currencies_in_csv = currencies_in_csv.intersection(set(currencies_to_import))
        
        if len(currencies_in_csv) > 0:
            # Multi-currency Revolut import - create accounts and import per currency
            results = []
            
            # Determine account name prefix based on bank type
            account_prefix = "Revolut"
            if "Crypto" in bank_name or account.account_type == "Revolut crypto":
                account_prefix = "Revolut Crypto"
            elif "Stock" in bank_name or account.account_type == "Revolut stock":
                account_prefix = "Revolut Stock"
            
            for currency in currencies_in_csv:
                # Get or create currency-specific account
                account_name = f"{account_prefix} {currency}"
                account_type = f"{account_prefix} {currency}"
                
                currency_account = db.query(Account).filter(
                    Account.user_id == current_user.id,
                    Account.institution_id == "MANUAL_CSV",
                    Account.account_type == account_type,
                    Account.currency == currency
                ).first()
                
                if not currency_account:
                    # Create account for this currency
                    currency_account = Account(
                        id=f"manual_csv_{uuid.uuid4()}",
                        user_id=current_user.id,
                        institution_id="MANUAL_CSV",
                        requisition_id=None,
                        name=account_name,
                        account_type=account_type,
                        currency=currency,
                        source_type="csv_manual"
                    )
                    db.add(currency_account)
                    db.flush()
                
                # Filter transactions for this currency
                currency_transactions = [tx for tx in csv_transactions if tx.currency == currency]
                
                # Import transactions for this currency
                batch = ImportBatch(
                    id=str(uuid.uuid4()),
                    account_id=currency_account.id,
                    user_id=current_user.id,
                    filename=f"{file.filename} ({currency})",
                    bank_name=f"Revolut {currency}",
                    transaction_count=len(currency_transactions),
                    status="processing"
                )
                db.add(batch)
                db.flush()
                
                imported_count = 0
                duplicate_count = 0
                error_count = 0
                errors = []
                
                for row_idx, csv_tx in enumerate(currency_transactions, 1):
                    try:
                        tx_hash = generate_transaction_hash(
                            currency_account.id,
                            csv_tx.booking_date,
                            float(csv_tx.amount),
                            csv_tx.description,
                            csv_tx.counterparty
                        )
                        
                        existing = db.query(Transaction).filter(
                            Transaction.account_id == currency_account.id,
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
                        
                        transaction = Transaction(
                            id=str(uuid.uuid4()),
                            account_id=currency_account.id,
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
                        
                        _auto_categorize_transaction(db, transaction, current_user.id)
                        
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
                        continue
                
                batch.imported_count = imported_count
                batch.duplicate_count = duplicate_count
                batch.error_count = error_count
                batch.status = "completed" if error_count == 0 else "partial"
                batch.completed_at = datetime.utcnow()
                if errors:
                    batch.error_details = "\n".join(errors[:50])
                
                results.append({
                    "currency": currency,
                    "account_id": currency_account.id,
                    "batch_id": batch.id,
                    "imported": imported_count,
                    "duplicates": duplicate_count,
                    "errors": error_count
                })
            
            db.commit()
            
            # Delete the temporary "Revolut Multi-Currency" account if it exists
            temp_account = db.query(Account).filter(
                Account.id == account_id,
                Account.user_id == current_user.id,
                Account.name.in_(["Revolut Multi-Currency", "Revolut Crypto Multi-Currency", "Revolut Stock Multi-Currency"])
            ).first()
            if temp_account:
                db.delete(temp_account)
                db.commit()
            
            total_imported = sum(r["imported"] for r in results)
            total_duplicates = sum(r["duplicates"] for r in results)
            total_errors = sum(r["errors"] for r in results)
            
            return {
                "message": f"Multi-currency import completed: {len(currencies_in_csv)} accounts created/used",
                "accounts_created": len(currencies_in_csv),
                "total_imported": total_imported,
                "total_duplicates": total_duplicates,
                "total_errors": total_errors,
                "details": results,
                "temp_account_deleted": temp_account is not None
            }
    
    # Single-currency import (original logic)
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
