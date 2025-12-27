#!/usr/bin/env python3
from app.db.session import SessionLocal
from app.models import Transaction, Account
from sqlalchemy import or_
from datetime import datetime

db = SessionLocal()
user_id = db.query(Account).first().user_id if db.query(Account).first() else None
if not user_id:
    print('No user found')
    exit()

start = datetime(2024, 11, 1)
end = datetime(2024, 12, 31)

accounts = db.query(Account).filter(Account.user_id == user_id).all()
account_ids = [a.id for a in accounts]

print(f"\nAnalyzing transactions in Nov-Dec 2024...\n")

# Get Revolut card payments FROM Raiffeisen (outgoing/expense)
raiff_to_revolut = db.query(Transaction).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start,
    Transaction.booking_date <= end,
    Transaction.amount < 0,
    or_(
        Transaction.description.ilike('%revolut%'),
        Transaction.counterparty.ilike('%revolut%')
    )
).order_by(Transaction.booking_date).limit(20).all()

print(f"=== OUTGOING to Revolut (expenses, should be internal) ===")
for tx in raiff_to_revolut:
    acc = next((a for a in accounts if a.id == tx.account_id), None)
    acc_name = (acc.name if acc else 'Unknown')[:20]
    internal = 'YES' if tx.is_internal_transfer else 'NO '
    print(f'{tx.booking_date.date()} | {tx.amount:>10.2f} {tx.currency} | Int:{internal} | {acc_name:20} | {tx.description[:60]}')

print(f"\n=== INCOMING to Revolut (topups, should be internal) ===")
# Get Revolut topups (incoming/income)
revolut_topups = db.query(Transaction).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start,
    Transaction.booking_date <= end,
    Transaction.amount > 0,
    Transaction.description.ilike('%topup%')
).order_by(Transaction.booking_date).limit(20).all()

for tx in revolut_topups:
    acc = next((a for a in accounts if a.id == tx.account_id), None)
    acc_name = (acc.name if acc else 'Unknown')[:20]
    internal = 'YES' if tx.is_internal_transfer else 'NO '
    print(f'{tx.booking_date.date()} | +{tx.amount:>9.2f} {tx.currency} | Int:{internal} | {acc_name:20} | {tx.description[:60]}')

print(f"\n=== FX Conversions (should be internal) ===")
fx_conversions = db.query(Transaction).filter(
    Transaction.account_id.in_(account_ids),
    Transaction.booking_date >= start,
    Transaction.booking_date <= end,
    Transaction.description.ilike('%exchanged to%')
).order_by(Transaction.booking_date).limit(20).all()

for tx in fx_conversions:
    acc = next((a for a in accounts if a.id == tx.account_id), None)
    acc_name = (acc.name if acc else 'Unknown')[:20]
    internal = 'YES' if tx.is_internal_transfer else 'NO '
    amt_sign = '+' if tx.amount >= 0 else ''
    print(f'{tx.booking_date.date()} | {amt_sign}{tx.amount:>9.2f} {tx.currency} | Int:{internal} | {acc_name:20} | {tx.description[:60]}')

db.close()
