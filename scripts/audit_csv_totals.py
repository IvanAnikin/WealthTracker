#!/usr/bin/env python3
"""
Audit CSV totals across multiple bank/export formats.

Supported sources (best-effort detection):
- Raiffeisen (Czech) bank statement CSV
- Revolut standard statement CSV
- Revolut crypto2 export
- Revolut stock2 export

Outputs total income and expenses per currency and an overall summary.

Usage:
    python scripts/audit_csv_totals.py --root /path/to/csv/folder

If --root is omitted, searches the current workspace for .csv files.
"""
import argparse
import csv
import json
import os
import re
from typing import Dict, List, Tuple, Optional

# ---------- Helpers ----------

def _strip(s: Optional[str]) -> str:
    return (s or "").strip()

def _to_float(raw: Optional[str]) -> float:
    """Convert commonly formatted numbers to float.
    Handles:
      - thousand separators ("," or space)
      - European decimals ("," decimal separator)
      - currency symbols and parentheses for negatives
    """
    s = _strip(raw)
    if not s:
        return 0.0

    # Handle negatives in parentheses e.g. (123.45)
    neg = False
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1]

    # Remove currency symbols and common decorations
    s = re.sub(r"[A-Za-z$€£¥₿]", "", s)  # strip currency letters/symbols
    s = s.replace("\xa0", " ")

    # Replace thousands separators
    # Heuristic: if there is both comma and dot, drop commas; if only comma, treat as decimal
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(" ", "")
        s = s.replace(",", ".")
    else:
        s = s.replace(" ", "")

    s = s.replace("+", "")

    try:
        val = float(s)
    except ValueError:
        # If still failing, strip any remaining non-numeric except dot and minus
        s2 = re.sub(r"[^0-9\.-]", "", s)
        val = float(s2) if s2 not in ("", ".", "-") else 0.0

    return -val if neg else val

# ---------- File type detection ----------

def detect_type(headers: List[str], filename: str) -> str:
    hs = [h.lower() for h in headers]
    fn = filename.lower()

    # Revolut standard CSV: Paid In / Paid Out / Completed Date / Reference
    if {'paid in', 'paid out'} <= set(hs) or ('completed date' in hs and 'description' in hs):
        return 'revolut'

    # Raiffeisen: Czech localized headers often include "Datum", "Popis", "Částka"
    if any('částka' in h for h in hs) or any('popis' in h for h in hs) or any('datum' in h for h in hs):
        return 'raiffeisen'

    # Revolut crypto2: headers commonly include "Type", "Symbol", "Quantity", "Price", "Fee", "Date"
    if {'type', 'symbol', 'quantity', 'price'} <= set(hs) or ('crypto' in fn and 'revolut' in fn):
        return 'revolut_crypto2'

    # Revolut stock2: headers include "Type", "Ticker/Symbol", "Quantity", "Price", "Total", "Currency"
    if ('stock' in fn and 'revolut' in fn) or {'type', 'total'} <= set(hs):
        return 'revolut_stock2'

    # Fallback generic
    return 'unknown'

def infer_currency_from_filename(filename: str) -> Optional[str]:
    fn = filename.upper()
    for cur in ['CZK', 'EUR', 'USD', 'GBP', 'PLN']:
        if cur in fn:
            return cur
    return None

# ---------- Parsers ----------

def parse_revolut(row: Dict[str, str], filename: Optional[str] = None) -> Optional[Tuple[str, float]]:
    # Typical fields: Paid In, Paid Out, Currency
    currency = row.get('Currency') or row.get('Base Currency') or (infer_currency_from_filename(filename or '') or 'UNKNOWN')
    # Prefer direct Amount if present
    if row.get('Amount') is not None:
        amount = _to_float(row.get('Amount'))
    else:
        paid_in = _to_float(row.get('Paid In'))
        paid_out = _to_float(row.get('Paid Out'))
        amount = paid_in - paid_out
    # Skip zero rows
    if amount == 0.0:
        return None
    return (currency, amount)

def parse_raiffeisen(row: Dict[str, str], filename: Optional[str] = None, default_currency: str = 'CZK') -> Optional[Tuple[str, float]]:
    # Common headers: "Částka" or "Amount"; currency may be absent (assume CZK)
    currency = row.get('Měna') or row.get('Currency') or infer_currency_from_filename(filename or '') or default_currency
    raw_amount = row.get('Částka') or row.get('Amount') or row.get('Castka')
    if raw_amount is None:
        # Some exports split Debit/Credit
        credit = row.get('Credit')
        debit = row.get('Debit')
        if credit or debit:
            amount = _to_float(credit) - _to_float(debit)
        else:
            return None
    else:
        amount = _to_float(raw_amount)
    if amount == 0.0:
        return None
    return (currency, amount)

def parse_revolut_crypto2(row: Dict[str, str], filename: Optional[str] = None) -> Optional[Tuple[str, float]]:
    # Prefer crypto tax export fields
    currency = row.get('Currency') or row.get('Base Currency') or row.get('Fiat Currency') or (infer_currency_from_filename(filename or '') or 'UNKNOWN')
    gross_proceeds = _to_float(row.get('Gross proceeds'))
    cost_basis = _to_float(row.get('Cost basis'))
    fees = _to_float(row.get('Fees'))
    net_pnl = _to_float(row.get('Net PnL'))
    # Cash flow approximation: income = gross_proceeds; expense = cost_basis + fees
    amt = gross_proceeds - cost_basis - fees
    if amt == 0.0:
        # fallback to generic fields
        total = row.get('Total') or row.get('Value') or row.get('Fiat Amount')
        amt = _to_float(total)
    if amt == 0.0 and net_pnl != 0.0:
        amt = net_pnl
    if amt == 0.0:
        return None
    return (currency, amt)

def parse_revolut_stock2(row: Dict[str, str], filename: Optional[str] = None) -> Optional[Tuple[str, float]]:
    currency = row.get('Currency') or row.get('Base Currency') or (infer_currency_from_filename(filename or '') or 'UNKNOWN')
    total = row.get('Total Amount') or row.get('Total') or row.get('Value')
    type_ = (row.get('Type') or '').lower()
    amt = _to_float(total)
    if amt == 0.0:
        # Try Paid In / Paid Out if present
        paid_in = _to_float(row.get('Paid In'))
        paid_out = _to_float(row.get('Paid Out'))
        amt = paid_in - paid_out
    if amt == 0.0 and type_:
        qty = _to_float(row.get('Quantity'))
        price = _to_float(row.get('Price'))
        if qty != 0.0 and price != 0.0:
            amt = qty * price
            if 'buy' in type_:
                amt = -abs(amt)
            elif 'sell' in type_:
                amt = abs(amt)
    if amt == 0.0:
        return None
    return (currency, amt)

def parse_unknown(row: Dict[str, str]) -> Optional[Tuple[str, float]]:
    # Generic heuristic: Currency column and either Amount OR Paid In/Out
    currency = row.get('Currency') or row.get('Měna') or row.get('Base Currency') or 'UNKNOWN'
    amount = row.get('Amount') or row.get('Částka') or row.get('Castka')
    if amount is not None:
        amt = _to_float(amount)
    else:
        amt = _to_float(row.get('Paid In')) - _to_float(row.get('Paid Out'))
    if amt == 0.0:
        return None
    return (currency, amt)

# ---------- Aggregation ----------

def aggregate_file(path: str) -> Dict[str, Dict[str, float]]:
    """Aggregate one file into income/expenses per currency."""
    per_currency: Dict[str, Dict[str, float]] = {}
    encodings = ['utf-8-sig', 'utf-8', 'cp1250', 'latin-1']
    last_err = None
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ';' if ';' in sample and ',' not in sample else ','
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames or []
                ftype = detect_type(headers, os.path.basename(path))
                print(f"Parsing {path} (encoding={enc}) type={ftype} headers={headers}")

                for row in reader:
                    cur_amt: Optional[Tuple[str, float]] = None
                    if ftype == 'revolut':
                        cur_amt = parse_revolut(row, os.path.basename(path))
                    elif ftype == 'raiffeisen':
                        cur_amt = parse_raiffeisen(row, os.path.basename(path))
                    elif ftype == 'revolut_crypto2':
                        cur_amt = parse_revolut_crypto2(row, os.path.basename(path))
                    elif ftype == 'revolut_stock2':
                        cur_amt = parse_revolut_stock2(row, os.path.basename(path))
                    else:
                        cur_amt = parse_unknown(row)

                    if cur_amt is None:
                        continue
                    currency, amount = cur_amt
                    bucket = per_currency.setdefault(currency, {'income': 0.0, 'expenses': 0.0})
                    if amount >= 0:
                        bucket['income'] += amount
                    else:
                        bucket['expenses'] += abs(amount)
            # If succeeded, break out
            last_err = None
            break
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err

    return per_currency

# ---------- Main ----------

def find_csv_files(root: str) -> List[str]:
    files: List[str] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.csv'):
                files.append(os.path.join(dirpath, fn))
    return files


def main():
    parser = argparse.ArgumentParser(description='Audit totals across CSV bank exports (income/expenses per currency).')
    parser.add_argument('--root', type=str, default=os.getcwd(), help='Root folder to search for CSV files')
    parser.add_argument('--save', type=str, default='audit_totals.json', help='Where to save JSON summary')
    args = parser.parse_args()

    csv_files = find_csv_files(args.root)
    if not csv_files:
        print(f"No CSV files found under {args.root}")
        return

    print(f"Found {len(csv_files)} CSV files. Aggregating...")

    per_file: Dict[str, Dict[str, Dict[str, float]]] = {}
    grand: Dict[str, Dict[str, float]] = {}

    for path in csv_files:
        try:
            totals = aggregate_file(path)
            per_file[path] = totals
            for cur, agg in totals.items():
                g = grand.setdefault(cur, {'income': 0.0, 'expenses': 0.0})
                g['income'] += agg.get('income', 0.0)
                g['expenses'] += agg.get('expenses', 0.0)
        except Exception as e:
            print(f"⚠️  Failed to parse {path}: {e}")

    # Break grand totals into income/expenses per currency
    summary: Dict[str, Dict[str, float]] = {}
    for cur, agg in grand.items():
        income = round(agg.get('income', 0.0), 2)
        expenses = round(agg.get('expenses', 0.0), 2)
        summary[cur] = {
            'income': income,
            'expenses': expenses,
            'net': round(income - expenses, 2)
        }

    result = {
        'root': args.root,
        'file_count': len(csv_files),
        'per_file': per_file,
        'summary_by_currency': summary
    }

    with open(args.save, 'w', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)

    print("\nSummary by currency:")
    for cur, agg in summary.items():
        print(f"  {cur}: income={agg['income']:.2f}, expenses={agg['expenses']:.2f}, net={agg['net']:.2f}")
    print(f"\nSaved detailed breakdown to {args.save}")

if __name__ == '__main__':
    main()
