#!/usr/bin/env python3
"""Check if report filters are excluding internal transfers correctly."""
from app.db.session import SessionLocal
from app.models import Transaction, Account
from sqlalchemy import func, extract, case
from datetime import datetime

db = SessionLocal()
user_id = db.query(Account).first().user_id if db.query(Account).first() else None

start_date = datetime(2024, 11, 1)
end_date = datetime(2024, 12, 31)

accounts = db.query(Account).filter(Account.user_id == user_id).all()
account_ids = [a.id for a in accounts]

print("\n=== Testing Report Query Logic ===\n")

# Test 1: Count all transactions
all_count = db.query(func.count(Transaction.id)).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked'
).scalar()

print(f"Total transactions (Nov-Dec 2024): {all_count}")

# Test 2: Count with is_internal_transfer filter
non_internal_count = db.query(func.count(Transaction.id)).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked',
    Transaction.is_internal_transfer == False
).scalar()

print(f"Non-internal transactions: {non_internal_count}")
print(f"Internal transactions: {all_count - non_internal_count}")

# Test 3: Count with description pattern filters
pattern_excluded = db.query(func.count(Transaction.id)).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked',
    Transaction.is_internal_transfer == False,
    ~Transaction.description.ilike('%exchanged to %'),
    ~Transaction.description.ilike('%revolut bank uab%'),
    ~Transaction.description.ilike('%revolut digital assets%'),
    ~Transaction.description.ilike('%transfer to revolut digital assets%'),
    ~Transaction.description.ilike('%transfer to my account%'),
    ~Transaction.description.ilike('%konverze%')
).scalar()

print(f"After pattern exclusions: {pattern_excluded}")

# Test 4: Break down by amount sign
income_case = case((Transaction.amount >= 0, Transaction.amount), else_=0)
expense_case = case((Transaction.amount < 0, Transaction.amount), else_=0)

# Without filters
all_stats = db.query(
    func.sum(income_case).label('income'),
    func.sum(expense_case).label('expenses'),
    func.count(Transaction.id).label('count')
).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked'
).first()

print(f"\n=== Without Exclusions ===")
print(f"Income: {all_stats.income:,.2f} CZK")
print(f"Expenses: {abs(all_stats.expenses):,.2f} CZK")
print(f"Net: {all_stats.income + all_stats.expenses:,.2f} CZK")

# With is_internal_transfer filter only
filtered_stats = db.query(
    func.sum(income_case).label('income'),
    func.sum(expense_case).label('expenses'),
    func.count(Transaction.id).label('count')
).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked',
    Transaction.is_internal_transfer == False
).first()

print(f"\n=== With is_internal_transfer == False ===")
print(f"Income: {filtered_stats.income:,.2f} CZK")
print(f"Expenses: {abs(filtered_stats.expenses):,.2f} CZK")
print(f"Net: {filtered_stats.income + filtered_stats.expenses:,.2f} CZK")

# With pattern filters
pattern_filtered_stats = db.query(
    func.sum(income_case).label('income'),
    func.sum(expense_case).label('expenses'),
    func.count(Transaction.id).label('count')
).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.status == 'booked',
    Transaction.is_internal_transfer == False,
    ~Transaction.description.ilike('%exchanged to %'),
    ~Transaction.description.ilike('%revolut bank uab%'),
    ~Transaction.description.ilike('%revolut digital assets%'),
    ~Transaction.description.ilike('%transfer to revolut digital assets%'),
    ~Transaction.description.ilike('%transfer to my account%'),
    ~Transaction.description.ilike('%konverze%')
).first()

print(f"\n=== With Pattern Exclusions ===")
print(f"Income: {pattern_filtered_stats.income:,.2f} CZK")
print(f"Expenses: {abs(pattern_filtered_stats.expenses):,.2f} CZK")
print(f"Net: {pattern_filtered_stats.income + pattern_filtered_stats.expenses:,.2f} CZK")

# Check if any Revolut card payments are NOT marked internal
print(f"\n=== Checking for unmarked Revolut card payments ===")
unmarked_revolut = db.query(Transaction).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start_date,
    Transaction.booking_date <= end_date,
    Transaction.is_internal_transfer == False,
    Transaction.description.ilike('%revolut%'),
    Transaction.amount < 0
).limit(10).all()

if unmarked_revolut:
    print(f"Found {len(unmarked_revolut)} unmarked outgoing Revolut transactions:")
    for tx in unmarked_revolut:
        acc = next((a for a in accounts if a.id == tx.account_id), None)
        print(f"  {tx.booking_date.date()} | {tx.amount:>10.2f} | {acc.name if acc else 'Unknown'} | {tx.description[:60]}")
else:
    print("All Revolut card payments are correctly marked as internal")

db.close()
