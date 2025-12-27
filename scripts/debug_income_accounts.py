import sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db.session import SessionLocal
from app.models import Transaction, Account
from collections import defaultdict

with SessionLocal() as db:
    # Get all incomes excluding internal transfers
    incomes = db.query(Transaction).join(Account).filter(
        Transaction.amount > 0,
        Transaction.is_internal_transfer == False
    ).all()
    
    print(f"Total income transactions (excluding internal): {len(incomes)}")
    
    # Group by account
    by_account = defaultdict(lambda: {"count": 0, "amount": 0.0, "name": None, "type": None})
    for t in incomes:
        acc = t.account
        by_account[acc.id]["count"] += 1
        by_account[acc.id]["amount"] += float(t.amount or 0)
        by_account[acc.id]["name"] = acc.name or acc.account_type or acc.id
        by_account[acc.id]["type"] = acc.account_type
    
    print("\nAccounts with income (excluding internal):")
    for acc_id, data in sorted(by_account.items(), key=lambda x: x[1]["amount"], reverse=True):
        print(f"  {acc_id}: {data['name']} ({data['type']}) - {data['amount']:.2f} ({data['count']} txs)")
