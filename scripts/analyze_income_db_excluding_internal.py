from collections import defaultdict
import sys, os
from sqlalchemy.orm import Session

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db.session import SessionLocal
from app.models import Transaction, Account, TransactionCategory, Category


def analyze_income(db: Session):
    q = db.query(Transaction).join(Account)
    incomes = q.filter(Transaction.amount > 0, Transaction.is_internal_transfer == False).all()
    print(f"Income transactions in DB (excluding internal transfers): {len(incomes)}")
    if not incomes:
        return

    by_account = defaultdict(lambda: {"count": 0, "amount": 0.0, "currency": None, "name": None, "institution": None})
    by_category = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_institution = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_type = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_counterparty = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_desc_keywords = defaultdict(lambda: {"count": 0, "amount": 0.0})

    # Preload transaction->categories mapping
    tx_to_cats = defaultdict(list)
    tc_rows = db.query(TransactionCategory).all()
    cat_map = {c.id: c.name for c in db.query(Category).all()}
    for tc in tc_rows:
        tx_to_cats[tc.transaction_id].append(cat_map.get(tc.category_id, tc.category_id))

    for t in incomes:
        acc = t.account
        key = acc.id
        by_account[key]["count"] += 1
        by_account[key]["amount"] += float(t.amount or 0)
        by_account[key]["currency"] = acc.currency
        by_account[key]["name"] = acc.name or acc.account_type or key
        by_account[key]["institution"] = acc.institution_id
        by_institution[acc.institution_id]["count"] += 1
        by_institution[acc.institution_id]["amount"] += float(t.amount or 0)
        by_type[(acc.account_type or "").strip() or "<unknown>"]["count"] += 1
        by_type[(acc.account_type or "").strip() or "<unknown>"]["amount"] += float(t.amount or 0)
        cp = (t.counterparty or "").strip() or "<none>"
        by_counterparty[cp]["count"] += 1
        by_counterparty[cp]["amount"] += float(t.amount or 0)
        cats = tx_to_cats.get(t.id) or ["Uncategorized"]
        for c in cats:
            by_category[c]["count"] += 1
            by_category[c]["amount"] += float(t.amount or 0)

        # Heuristic keywords in description
        desc = (t.description or "").lower()
        kw_map = {
            "salary": ["salary", "payroll", "mzda", "vyplata"],
            "bonus": ["bonus"],
            "interest": ["interest", "úrok", "urok"],
            "cashback": ["cashback", "revolut cashback"],
            "refund": ["refund", "refunded", "vrat"],
            "dividend": ["dividend", "dividenda"],
            "crypto_sale": ["crypto", "bitcoin", "btc", "eth"],
            "stock_sale": ["stock", "share"],
        }
        matched = False
        for k, kws in kw_map.items():
            if any(kw in desc for kw in kws):
                by_desc_keywords[k]["count"] += 1
                by_desc_keywords[k]["amount"] += float(t.amount or 0)
                matched = True
                break
        if not matched:
            by_desc_keywords["uncategorized"]["count"] += 1
            by_desc_keywords["uncategorized"]["amount"] += float(t.amount or 0)

    def top_print(title, data, fmt_name=None):
        print(f"\n=== Top income by {title} (excluding internal transfers) ===")
        top = sorted(data.items(), key=lambda x: x[1]["amount"], reverse=True)[:10]
        for name, stats in top:
            disp = fmt_name(name, stats) if fmt_name else name
            amt = stats["amount"]
            cnt = stats["count"]
            print(f"{str(disp)[:40]:40s}  count={cnt:4d}  amount={amt:,.2f}")

    top_print("category", by_category)
    top_print("institution", by_institution)
    top_print("account_type", by_type)
    top_print("account", by_account, fmt_name=lambda n, s: f"{s['name']} [{n}] ({s['institution']}, {s['currency']})")
    top_print("counterparty", by_counterparty)
    top_print("description_keywords", by_desc_keywords)


if __name__ == "__main__":
    with SessionLocal() as db:
        analyze_income(db)
