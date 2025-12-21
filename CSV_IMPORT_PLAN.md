# CSV Transaction Import Implementation Plan

## Overview
Transitioning from Open Banking API integration (Tink) to CSV file upload for transaction management. This allows direct import of bank statements without depending on external APIs.

## Architecture

### 1. CSV Parser Layer (`app/services/csv_parsers/`)
**Purpose**: Parse bank-specific CSV formats into a unified transaction format

#### Supported Banks:
1. **Raiffeisen** (Main & Sporící accounts)
   - Format: Semicolon-delimited, Czech locale (commas for decimals)
   - Key fields: Datum provedení, Datum zúčtování, Číslo účtu, Zaúčtovaná částka, Měna, Protiúčet, Zpráva
   
2. **Revolut** Variants:
   - **Current Account (CZK/EUR/USD)**: Comma-delimited
     - Fields: Type, Product, Started Date, Completed Date, Description, Amount, Fee, Currency
   - **Crypto**: CSV format with Symbol, Type, Quantity, Price, Value, Fees, Date
   - **Stock**: Multiple sections (Income from Sells, Other income & fees)

### 2. Models Enhancement
- Add `ImportBatch` model to track CSV imports
- Enhance `Account` model with manual account type support
- Add `TransactionSource` enum (API vs CSV)
- Track import metadata (filename, import date, row count)

### 3. API Endpoints
```
POST /accounts/manual - Create manual account
POST /accounts/{id}/import-csv - Upload and parse CSV
GET /accounts/{id}/import-history - View import history
DELETE /accounts/{id}/imports/{batch_id} - Delete import batch
```

### 4. UI Changes
**New Page**: `/ui/accounts/import` or modal in accounts page
- Account type selector (Raiffeisen main, Raiffeisen sporici, Revolut variants)
- File upload input
- Preview of parsed transactions
- Confirmation and import button
- Import history with rollback option

## Implementation Steps

### Phase 1: Core CSV Parsers (Priority: HIGH)
1. Create `CSVParser` abstract base class
2. Implement `RaiffeisenParser`
3. Implement `RevolutCurrentParser`
4. Implement `RevolutCryptoParser`
5. Implement `RevolutStockParser`
6. Tests for each parser

### Phase 2: Data Models (Priority: HIGH)
1. Create `ImportBatch` model
2. Update `Account` model with `source_type` field
3. Add enum: `AccountSourceType` (API, CSV_MANUAL)
4. Create `TransactionImportLog` for tracking

### Phase 3: API Layer (Priority: HIGH)
1. Create `/api/imports.py` router
2. Implement account creation endpoint
3. Implement CSV upload endpoint
4. Implement preview endpoint (dry-run)
5. Implement confirmation endpoint

### Phase 4: UI Layer (Priority: MEDIUM)
1. Create import modal/page
2. Add file upload component
3. Add account type selector
4. Display preview with validation
5. Show success/error messages
6. Display import history

### Phase 5: Testing (Priority: MEDIUM)
1. Unit tests for each parser
2. Integration tests for import flow
3. Edge case handling (duplicates, encoding, validation)

## CSV Format Analysis

### Raiffeisen (Czech locale, semicolon-delimited, UTF-8 encoding)
```
Datum provedení;Datum zúčtování;Číslo účtu;Název účtu;Kategorie transakce;Číslo protiúčtu;Název protiúčtu;Typ transakce;Zpráva;Poznámka;VS;KS;SS;Zaúčtovaná částka;Měna účtu;...
"06.12.2025";"09.12.2025 06:12";"6696675002/5500";"Ivan Sergejević Anik";"Platba kartou";"408359XXXXXX1082";"";"Platba na internetu Apple Pay";"Revolut**5813*; Dublin; IRL";"Revolut**5813*; Dublin; IRL";"";"1178";"";"-300,00";"CZK";...
```

**Key mappings**:
- `Datum provedení` → booking_date
- `Datum zúčtování` → value_date
- `Zaúčtovaná částka` → amount (handle comma as decimal)
- `Měna účtu` → currency
- `Zpráva` or `Název protiúčtu` → description/counterparty
- `Číslo transakce` or generate hash → transaction_id

### Revolut Current Account (Comma-delimited, ISO format)
```
Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance
Transfer,Current,2020-09-04 10:33:53,2020-09-04 10:33:53,Transfer from SERGEJ ANIKIN,300.00,0.00,CZK,COMPLETED,300.00
Card Payment,Current,2020-09-18 19:16:59,2020-09-19 13:48:02,Tesco,-46.60,0.00,CZK,COMPLETED,1105.41
```

**Key mappings**:
- `Completed Date` → booking_date & value_date
- `Description` → description
- `Amount` → amount
- `Fee` → separate transaction or add to description
- `Currency` → currency

### Revolut Crypto (Symbol, Type, Quantity, Price, Value, Fees, Date)
```
Symbol,Type,Quantity,Price,Value,Fees,Date
BTC,Buy,0.003672,"1,089,324.62 CZK","4,000.00 CZK",19.99 CZK,"Dec 6, 2021, 12:44:18 PM"
```

**Handling**:
- Create as investment transaction (new type)
- Symbol as counterparty
- Value (not quantity) as amount
- Include fees in description

### Revolut Stock (Multiple sections, complex structure)
```
Date acquired,Date sold,Symbol,Security name,ISIN,Quantity,Cost basis,Gross proceeds,Gross PnL,Currency
2024-11-26,2025-10-20,INTC,Intel,US4581401001,1.00170272,25.00,37.64,12.64,USD
```

**Handling**:
- Parse "Income from Sells" section for stock sales
- Parse "Other income & fees" for dividends
- Create investment transactions
- Include security name in description

## Testing Data Provided
- Raiffeisen: 334 transactions
- Revolut Current: 4041 transactions
- Revolut Crypto: 301 transactions
- Revolut Stock: Multiple sections with income events

## Risk Mitigation
1. **Dry-run preview** before actual import
2. **Deduplication** by transaction hash
3. **Import batches** with ability to rollback
4. **Validation** of required fields
5. **Encoding detection** for CSV files
6. **Error reporting** with line numbers

## Timeline
- Phase 1-2: 30 mins (parsers + models)
- Phase 3: 20 mins (API endpoints)
- Phase 4: 25 mins (UI)
- Phase 5: 15 mins (testing)
- **Total: ~90 mins**
