"""CSV transaction parsers for different banks."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import csv
import io
from decimal import Decimal


class CSVTransaction:
    """Unified transaction representation from CSV."""
    
    def __init__(
        self,
        booking_date: datetime,
        amount: Decimal,
        currency: str,
        description: str,
        counterparty: Optional[str] = None,
        value_date: Optional[datetime] = None,
        transaction_id: Optional[str] = None,
        original_id: Optional[str] = None,
        transaction_type: str = "payment",  # payment, transfer, investment, etc.
        fees: Decimal = Decimal("0"),
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.booking_date = booking_date
        self.value_date = value_date or booking_date
        self.amount = amount
        self.currency = currency
        self.description = description
        self.counterparty = counterparty or ""
        self.transaction_id = transaction_id
        self.original_id = original_id  # For deduplication
        self.transaction_type = transaction_type
        self.fees = fees
        self.metadata = metadata or {}


class CSVParser(ABC):
    """Abstract base class for CSV parsers."""
    
    @abstractmethod
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse CSV content and return list of transactions."""
        pass
    
    @abstractmethod
    def detect(self, file_content: str) -> bool:
        """Detect if this parser can handle the CSV file."""
        pass
    
    @staticmethod
    def parse_czech_decimal(value: str) -> Decimal:
        """Parse Czech locale decimal (comma as separator)."""
        if not value:
            return Decimal("0")
        # Remove thousands separator (space or nothing)
        value = value.replace(" ", "").strip()
        # Replace comma with dot for Decimal parsing
        value = value.replace(",", ".")
        try:
            return Decimal(value)
        except:
            return Decimal("0")
    
    @staticmethod
    def parse_iso_decimal(value: str) -> Decimal:
        """Parse ISO decimal (dot as separator)."""
        if not value:
            return Decimal("0")
        try:
            return Decimal(value.strip())
        except:
            return Decimal("0")


class RaiffeisenParser(CSVParser):
    """Parser for Raiffeisen bank CSV exports (Czech)."""
    
    def detect(self, file_content: str) -> bool:
        """Detect Raiffeisen format by header."""
        return "Datum provedení" in file_content and "Číslo účtu" in file_content
    
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse Raiffeisen CSV with Czech locale."""
        transactions = []
        
        # Handle different encodings
        lines = file_content.split('\n')
        
        # Skip empty lines and find header
        lines = [l for l in lines if l.strip()]
        if not lines:
            return transactions
        
        # Parse as semicolon-delimited with quotes
        reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=';')
        
        for row in reader:
            try:
                # Parse dates
                booking_date_str = row.get('Datum provedení', '').strip('"')
                value_date_str = row.get('Datum zúčtování', '').strip('"')
                
                try:
                    booking_date = datetime.strptime(booking_date_str, "%d.%m.%Y")
                except:
                    continue
                
                try:
                    # Value date has time component
                    value_date = datetime.strptime(value_date_str, "%d.%m.%Y %H:%M")
                except:
                    value_date = booking_date
                
                # Parse amount
                amount_str = row.get('Zaúčtovaná částka', '0').strip('"')
                amount = self.parse_czech_decimal(amount_str)
                
                if amount == 0:
                    continue
                
                currency = row.get('Měna účtu', 'CZK').strip('"')
                
                # Determine description and counterparty
                zprava = row.get('Zpráva', '').strip('"')
                poznamka = row.get('Poznámka', '').strip('"')
                nazev_protiuctu = row.get('Název protiúčtu', '').strip('"')
                typ_transakce = row.get('Typ transakce', '').strip('"')
                
                description = f"{typ_transakce}: {zprava}" if zprava else typ_transakce
                counterparty = nazev_protiuctu or ""
                
                # Transaction ID from the bank
                trans_id_str = row.get('Id transakce', '').strip('"')
                
                fees = self.parse_czech_decimal(row.get('Poplatek', '0').strip('"'))
                
                transaction = CSVTransaction(
                    booking_date=booking_date,
                    value_date=value_date,
                    amount=amount,
                    currency=currency,
                    description=description,
                    counterparty=counterparty,
                    original_id=trans_id_str,
                    transaction_id=trans_id_str,
                    fees=fees,
                    metadata={
                        'vs': row.get('VS', '').strip('"'),
                        'ks': row.get('KS', '').strip('"'),
                        'ss': row.get('SS', '').strip('"'),
                        'typ_transakce': typ_transakce,
                        'poznamka': poznamka,
                    }
                )
                transactions.append(transaction)
            except Exception as e:
                print(f"Error parsing Raiffeisen row: {e}")
                continue
        
        return transactions


class RevolutCurrentParser(CSVParser):
    """Parser for Revolut current account CSV exports."""
    
    def detect(self, file_content: str) -> bool:
        """Detect Revolut format by header."""
        return "Type,Product,Started Date" in file_content or "Type" in file_content and "Started Date" in file_content
    
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse Revolut CSV."""
        transactions = []
        
        lines = file_content.split('\n')
        lines = [l for l in lines if l.strip()]
        
        if not lines:
            return transactions
        
        reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=',')
        
        for row in reader:
            try:
                # Parse completed date
                completed_date_str = row.get('Completed Date', '').strip()
                
                try:
                    booking_date = datetime.fromisoformat(completed_date_str.replace('Z', '+00:00'))
                except:
                    try:
                        booking_date = datetime.strptime(completed_date_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        continue
                
                # Parse amount
                amount_str = row.get('Amount', '0').strip()
                amount = self.parse_iso_decimal(amount_str)
                
                if amount == 0:
                    continue
                
                currency = row.get('Currency', 'CZK').strip()
                description = row.get('Description', '').strip()
                
                # Parse fee
                fee_str = row.get('Fee', '0').strip()
                fee = self.parse_iso_decimal(fee_str)
                
                # Transaction type
                trans_type = row.get('Type', 'payment').strip().lower()
                if 'transfer' in trans_type:
                    trans_type = 'transfer'
                elif 'card' in trans_type:
                    trans_type = 'card_payment'
                else:
                    trans_type = 'payment'
                
                transaction = CSVTransaction(
                    booking_date=booking_date,
                    amount=amount,
                    currency=currency,
                    description=description,
                    transaction_type=trans_type,
                    fees=fee,
                    metadata={
                        'product': row.get('Product', ''),
                        'state': row.get('State', ''),
                        'balance': row.get('Balance', ''),
                    }
                )
                transactions.append(transaction)
            except Exception as e:
                print(f"Error parsing Revolut row: {e}")
                continue
        
        return transactions


class RevolutCryptoParser(CSVParser):
    """Parser for Revolut crypto transactions."""
    
    def detect(self, file_content: str) -> bool:
        """Detect Revolut crypto format."""
        return ("Date acquired,Date sold,Symbol" in file_content or 
                "Symbol,Type,Quantity,Price,Value" in file_content)
    
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse Revolut crypto CSV."""
        transactions = []
        
        lines = file_content.split('\n')
        lines = [l for l in lines if l.strip()]
        
        if not lines:
            return transactions
        
        reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=',')
        
        # Detect format by checking first row
        first_row = None
        try:
            first_row = next(csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=','))
        except:
            return transactions
        
        # New format: Date acquired, Date sold, Symbol, Quantity, Cost basis, Gross proceeds, Gross PnL, Fees, Net PnL, Currency
        is_new_format = 'Date acquired' in first_row and 'Date sold' in first_row
        
        # Re-create reader
        reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=',')
        
        for row in reader:
            try:
                if is_new_format:
                    # New format parsing
                    date_sold_str = row.get('Date sold', '').strip()
                    symbol = row.get('Symbol', '').strip()
                    
                    # Parse date
                    try:
                        booking_date = datetime.strptime(date_sold_str, "%Y-%m-%d")
                    except:
                        continue
                    
                    # Net PnL is the actual profit/loss
                    net_pnl_str = row.get('Net PnL', '0').strip()
                    amount = self.parse_iso_decimal(net_pnl_str)
                    
                    # Parse fees
                    fees_str = row.get('Fees', '0').strip()
                    fees = self.parse_iso_decimal(fees_str)
                    
                    # Get currency from CSV
                    currency = row.get('Currency', 'USD').strip()
                    
                    quantity = row.get('Quantity', '0').strip()
                    cost_basis = row.get('Cost basis', '0').strip()
                    gross_proceeds = row.get('Gross proceeds', '0').strip()
                    
                    description = f"SELL {quantity} {symbol} (Cost: {cost_basis}, Proceeds: {gross_proceeds}, PnL: {net_pnl_str})"
                    
                    transaction = CSVTransaction(
                        booking_date=booking_date,
                        amount=amount,
                        currency=currency,
                        description=description,
                        counterparty=f"{symbol} (Crypto)",
                        transaction_type='investment',
                        fees=fees,
                        metadata={
                            'symbol': symbol,
                            'action': 'sell',
                            'quantity': quantity,
                            'cost_basis': cost_basis,
                            'gross_proceeds': gross_proceeds,
                            'gross_pnl': row.get('Gross PnL', '').strip(),
                        }
                    )
                else:
                    # Old format parsing
                    symbol = row.get('Symbol', '').strip()
                    trans_type = row.get('Type', '').strip().lower()
                    date_str = row.get('Date', '').strip()
                    
                    # Parse date (various formats possible)
                    try:
                        booking_date = datetime.strptime(date_str, "%b %d, %Y, %I:%M:%S %p")
                    except:
                        try:
                            booking_date = datetime.fromisoformat(date_str)
                        except:
                            continue
                    
                    # Parse value (with potential "CZK" suffix)
                    value_str = row.get('Value', '0').strip()
                    # Remove currency suffix and commas
                    value_str = value_str.replace(',', '.').split()[0]
                    amount = self.parse_iso_decimal(value_str)
                    
                    if amount == 0:
                        continue
                    
                    # Parse fees
                    fees_str = row.get('Fees', '0').strip()
                    fees_str = fees_str.replace(',', '.').split()[0]
                    fees = self.parse_iso_decimal(fees_str)
                    
                    quantity = row.get('Quantity', '0').strip()
                    price = row.get('Price', '0').strip()
                    
                    description = f"{trans_type.upper()} {quantity} {symbol} @ {price}"
                    
                    transaction = CSVTransaction(
                        booking_date=booking_date,
                        amount=amount,
                        currency='CZK',  # Crypto values in CZK for old format
                        description=description,
                        counterparty=f"{symbol} (Crypto)",
                        transaction_type='investment',
                        fees=fees,
                        metadata={
                            'symbol': symbol,
                            'action': trans_type,
                            'quantity': quantity,
                            'price': price,
                        }
                    )
                
                transactions.append(transaction)
            except Exception as e:
                print(f"Error parsing Revolut crypto row: {e}")
                continue
        
        return transactions


class RevolutStockParser(CSVParser):
    """Parser for Revolut stock transactions."""
    
    def detect(self, file_content: str) -> bool:
        """Detect Revolut stock format."""
        return ("Date,Ticker,Type,Quantity,Price per share" in file_content or
                "Date acquired,Date sold,Symbol,Security name" in file_content)
    
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse Revolut stock CSV with multiple formats."""
        transactions = []
        
        lines = file_content.split('\n')
        lines = [l for l in lines if l.strip()]
        
        if not lines:
            return transactions
        
        # Detect format
        header = lines[0] if lines else ""
        is_new_format = "Date,Ticker,Type,Quantity,Price per share" in header
        
        if is_new_format:
            # New format: Date, Ticker, Type, Quantity, Price per share, Total Amount, Currency, FX Rate
            reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=',')
            
            for row in reader:
                try:
                    date_str = row.get('Date', '').strip()
                    ticker = row.get('Ticker', '').strip()
                    trans_type = row.get('Type', '').strip().upper()
                    
                    # Parse date (ISO format with Z timezone)
                    try:
                        booking_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        continue
                    
                    # Total Amount includes currency prefix
                    total_amount_str = row.get('Total Amount', '0').strip()
                    # Extract currency and amount (e.g., "USD 100" or "EUR 49.99")
                    parts = total_amount_str.split()
                    if len(parts) >= 2:
                        currency = parts[0]
                        amount_str = parts[1]
                    else:
                        currency = row.get('Currency', 'USD').strip()
                        amount_str = total_amount_str
                    
                    amount = self.parse_iso_decimal(amount_str)
                    
                    quantity = row.get('Quantity', '0').strip()
                    price = row.get('Price per share', '0').strip()
                    
                    # Build description based on transaction type
                    if 'CASH TOP-UP' in trans_type or 'CASH WITHDRAWAL' in trans_type:
                        description = trans_type
                        counterparty = "Cash Account"
                        transaction_type = 'transfer'
                    elif 'BUY' in trans_type:
                        description = f"BUY {quantity} x {ticker} @ {price}"
                        counterparty = f"{ticker} (Stock)"
                        transaction_type = 'investment'
                    elif 'SELL' in trans_type:
                        description = f"SELL {quantity} x {ticker} @ {price}"
                        counterparty = f"{ticker} (Stock)"
                        transaction_type = 'investment'
                    elif 'DIVIDEND' in trans_type:
                        description = f"DIVIDEND from {ticker}"
                        counterparty = f"{ticker} (Dividend)"
                        transaction_type = 'investment'
                    else:
                        description = f"{trans_type} {ticker}"
                        counterparty = ticker
                        transaction_type = 'payment'
                    
                    transaction = CSVTransaction(
                        booking_date=booking_date,
                        amount=amount,
                        currency=currency,
                        description=description,
                        counterparty=counterparty,
                        transaction_type=transaction_type,
                        metadata={
                            'ticker': ticker,
                            'action': trans_type,
                            'quantity': quantity,
                            'price_per_share': price,
                            'fx_rate': row.get('FX Rate', '').strip(),
                        }
                    )
                    transactions.append(transaction)
                except Exception as e:
                    print(f"Error parsing Revolut stock row (new format): {e}")
                    continue
        else:
            # Old format: Parse "Income from Sells" and "Other income & fees" sections
            # Parse "Income from Sells" section
            try:
                sells_idx = next(i for i, l in enumerate(lines) if "Income from Sells" in l)
                header_idx = next(i for i in range(sells_idx, len(lines)) if "Date acquired" in lines[i])
                
                sell_lines = []
                for i in range(header_idx + 1, len(lines)):
                    if lines[i].strip() == "" or "Other income" in lines[i]:
                        break
                    if lines[i].strip():
                        sell_lines.append(lines[i])
                
                if sell_lines:
                    reader = csv.DictReader(
                        io.StringIO('\n'.join([lines[header_idx]] + sell_lines)),
                        delimiter=','
                    )
                    
                    for row in reader:
                        try:
                            date_sold_str = row.get('Date sold', '').strip()
                            symbol = row.get('Symbol', '').strip()
                            security_name = row.get('Security name', '').strip()
                            
                            try:
                                booking_date = datetime.strptime(date_sold_str, "%Y-%m-%d")
                            except:
                                continue
                            
                            # Gross proceeds
                            proceeds_str = row.get('Gross proceeds', '0').strip()
                            amount = self.parse_iso_decimal(proceeds_str)
                            
                            if amount == 0:
                                continue
                            
                            currency = row.get('Currency', 'USD').strip()
                            quantity = row.get('Quantity', '0').strip()
                            
                            description = f"SELL {quantity} x {symbol} ({security_name})"
                            
                            transaction = CSVTransaction(
                                booking_date=booking_date,
                                amount=amount,
                                currency=currency,
                                description=description,
                                counterparty=f"{symbol} (Stock)",
                                transaction_type='investment',
                                metadata={
                                    'symbol': symbol,
                                    'security_name': security_name,
                                    'action': 'sell',
                                    'quantity': quantity,
                                }
                            )
                            transactions.append(transaction)
                        except Exception as e:
                            print(f"Error parsing stock sell row: {e}")
                            continue
            except:
                pass
            
            # Parse "Other income & fees" section (dividends)
            try:
                income_idx = next(i for i, l in enumerate(lines) if "Other income & fees" in l)
                header_idx = next(i for i in range(income_idx, len(lines)) if "Date,Symbol" in lines[i])
                
                income_lines = []
                for i in range(header_idx + 1, len(lines)):
                    if lines[i].strip() == "":
                        break
                    if lines[i].strip():
                        income_lines.append(lines[i])
                
                if income_lines:
                    reader = csv.DictReader(
                        io.StringIO('\n'.join([lines[header_idx]] + income_lines)),
                        delimiter=','
                    )
                    
                    for row in reader:
                        try:
                            date_str = row.get('Date', '').strip()
                            symbol = row.get('Symbol', '').strip()
                            security_name = row.get('Security name', '').strip()
                            
                            try:
                                booking_date = datetime.strptime(date_str, "%Y-%m-%d")
                            except:
                                continue
                            
                            # Net Amount
                            net_amount_str = row.get('Net Amount', '0').strip()
                            net_amount_str = net_amount_str.split()[0] if net_amount_str else '0'
                            amount = self.parse_iso_decimal(net_amount_str)
                            
                            if amount == 0:
                                continue
                            
                            currency = row.get('Currency', 'CZK').strip()
                            
                            # Withholding tax
                            wh_tax_str = row.get('Withholding tax', '0').strip()
                            wh_tax_str = wh_tax_str.replace('$', '').strip()
                            wh_tax = self.parse_iso_decimal(wh_tax_str)
                            
                            description = f"DIVIDEND {symbol} ({security_name})"
                            
                            transaction = CSVTransaction(
                                booking_date=booking_date,
                                amount=amount,
                                currency=currency,
                                description=description,
                                counterparty=f"{symbol} (Dividend)",
                                transaction_type='investment',
                                fees=wh_tax,
                                metadata={
                                    'symbol': symbol,
                                    'security_name': security_name,
                                    'action': 'dividend',
                                    'withholding_tax': str(wh_tax),
                                }
                            )
                            transactions.append(transaction)
                        except Exception as e:
                            print(f"Error parsing dividend row: {e}")
                            continue
            except:
                pass
        
        return transactions


class KomercniBankaParser(CSVParser):
    """Parser for Komerční banka CSV exports (Czech)."""
    
    def detect(self, file_content: str) -> bool:
        """Detect Komerční banka format by header."""
        first_line = file_content.split('\n')[0] if file_content else ""
        return 'Date,Wallet,Type,"Category name",Amount,Currency,Note,Labels,Author' in first_line
    
    def parse(self, file_content: str) -> List[CSVTransaction]:
        """Parse Komerční banka CSV."""
        transactions = []
        
        lines = file_content.split('\n')
        lines = [l for l in lines if l.strip()]
        if not lines:
            return transactions
        
        # Parse as comma-delimited CSV
        reader = csv.DictReader(io.StringIO('\n'.join(lines)))
        
        for row in reader:
            try:
                # Parse date (ISO 8601 format with timezone)
                date_str = row.get('Date', '').strip()
                if not date_str:
                    continue
                
                # Handle ISO 8601 format: 2024-12-23T11:00:00+00:00
                if 'T' in date_str:
                    # Remove timezone info for parsing
                    date_str = date_str.split('+')[0].split('-', 3)[:3]
                    date_str = '-'.join(date_str[:3])
                    if 'T' in date_str:
                        date_str = date_str.split('T')[0]
                
                booking_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Parse amount
                amount_str = row.get('Amount', '0').strip()
                amount = self.parse_iso_decimal(amount_str)
                
                # Get currency
                currency = row.get('Currency', 'CZK').strip()
                
                # Get description from Note field
                description = row.get('Note', '').strip()
                
                # Extract counterparty from description if available
                counterparty = ""
                if description:
                    # Try to extract counterparty from patterns like "Deposit, CZXXXX, Name"
                    parts = description.split(',')
                    if len(parts) >= 3:
                        counterparty = parts[2].strip()
                    elif len(parts) >= 2:
                        # For "Revolut**XXXX* Dublin IRL" type
                        counterparty = parts[0].strip()
                
                # Get transaction type
                tx_type = row.get('Type', '').strip().lower()
                
                # Create transaction
                transaction = CSVTransaction(
                    booking_date=booking_date,
                    value_date=booking_date,
                    amount=amount,
                    currency=currency,
                    description=description,
                    counterparty=counterparty,
                    transaction_type=tx_type if tx_type in ['expense', 'income'] else 'payment',
                    metadata={
                        'wallet': row.get('Wallet', '').strip(),
                        'category': row.get('Category name', '').strip(),
                        'labels': row.get('Labels', '').strip(),
                        'author': row.get('Author', '').strip()
                    }
                )
                
                transactions.append(transaction)
                
            except Exception as e:
                print(f"Error parsing KB row: {e}, row: {row}")
                continue
        
        return transactions


class CSVParserFactory:
    """Factory to detect and use appropriate parser."""
    
    PARSERS = [
        KomercniBankaParser(),
        RaiffeisenParser(),
        RevolutCryptoParser(),  # Try crypto before current (more specific)
        RevolutStockParser(),
        RevolutCurrentParser(),
    ]
    
    @classmethod
    def parse(cls, file_content: str) -> List[CSVTransaction]:
        """Auto-detect parser and parse CSV."""
        for parser in cls.PARSERS:
            if parser.detect(file_content):
                return parser.parse(file_content)
        
        # Fallback to generic CSV parsing
        return []
    
    @classmethod
    def detect_bank(cls, file_content: str) -> Optional[str]:
        """Detect which bank the CSV is from."""
        if KomercniBankaParser().detect(file_content):
            return "Komerční Banka"
        elif RaiffeisenParser().detect(file_content):
            return "Raiffeisen"
        elif RevolutCryptoParser().detect(file_content):
            return "Revolut Crypto"
        elif RevolutStockParser().detect(file_content):
            return "Revolut Stock"
        elif RevolutCurrentParser().detect(file_content):
            return "Revolut"
        return None
