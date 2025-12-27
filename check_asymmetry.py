#!/usr/bin/env python3
"""Analyze the asymmetry in internal transfer marking."""
from app.db.session import SessionLocal
from app.models import Transaction, Account
from sqlalchemy import func
from datetime import datetime

db = SessionLocal()
user_id = db.query(Account).first().user_id

start_date = datetime(2024, 11, 1)
end_date = datetime(2024, 12, 31)

accounts = db.query(Account).filter(Account.user_id == user_id).all()
account_ids = [a.id for a in accounts]

print("\n=== Internal Transfers Breakdown ===\n")

# Get all internal transfers
internal_txs = db.query(Transaction).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.is_internal_transfer == True
).order_by(Transaction.booking_date, Transaction.amount).all()

income_internal = [tx for tx in internal_txs if tx.amount >= 0]
expense_internal = [tx for tx in internal_txs if tx.amount < 0]

print(f"Internal Income transactions: {len(income_internal)}")
print(f"Internal Expense transactions: {len(expense_internal)}")

income_sum = sum(tx.amount for tx in income_internal)
expense_sum = sum(abs(tx.amount) for tx in expense_internal)

print(f"\nInternal Income total: {income_sum:,.2f} CZK")
print(f"Internal Expense total: {expense_sum:,.2f} CZK")
print(f"Difference: {abs(income_sum - expense_sum):,.2f} CZK")

# Show sample of each
print(f"\n=== Sample Internal Income (first 15) ===")
for tx in income_internal[:15]:
    acc = next((a for a in accounts if a.id == tx.account_id), None)
    acc_name = (acc.name if acc else 'Unknown')[:20]
    print(f'{tx.booking_date.date()} | +{tx.amount:>9.2f} {tx.currency} | {acc_name:20} | {tx.description[:55]}')

print(f"\n=== Sample Internal Expenses (first 15) ===")
for tx in expense_internal[:15]:
    acc = next((a for a in accounts if a.id == tx.account_id), None)
    acc_name = (acc.name if acc else 'Unknown')[:20]
    print(f'{tx.booking_date.date()} | {tx.amount:>10.2f} {tx.currency} | {acc_name:20} | {tx.description[:55]}')

# Check for unpaired transactions
print(f"\n=== Looking for Unpaired Internal Transfers ===")
for tx in income_internal:
    # Try to find matching outgoing
    match = next((t for t in expense_internal 
                  if abs(t.amount) == tx.amount 
                  and t.currency == tx.currency
                  and abs((t.booking_date - tx.booking_date).days) <= 3), None)
    if not match:
        acc = next((a for a in accounts if a.id == tx.account_id), None)
        print(f"UNPAIRED INCOME: {tx.booking_date.date()} | +{tx.amount:>9.2f} {tx.currency} | {acc.name if acc else 'Unknown'} | {tx.description[:50]}")

db.close()
