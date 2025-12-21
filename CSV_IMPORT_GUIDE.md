# CSV Import Guide

WealthTracker now supports importing transactions from CSV files for manual account management. This guide explains how to use the CSV import feature.

## Supported Banks & Account Types

### Raiffeisenbank (Czech Republic)
- **File Format**: Semicolon-delimited (`;`)
- **Encoding**: Windows-1250 (Czech)
- **Date Format**: DD.MM.YYYY and DD.MM.YYYY HH:MM
- **Amount Format**: Comma decimal (e.g., `-300,00` = -300.00)
- **Supported Accounts**:
  - Raiffeisenbank main account
  - Raiffeisenbank savings account (spořící)

### Revolut
- **File Format**: Comma-delimited (`,`)
- **Encoding**: UTF-8
- **Date Format**: ISO format (YYYY-MM-DD HH:MM:SS)
- **Amount Format**: Standard decimal (e.g., `-46.60`)
- **Supported Accounts**:
  - Revolut Current (CZK)
  - Revolut Current (EUR)
  - Revolut Current (USD)
  - Revolut Crypto (Bitcoin, Ethereum, etc.)
  - Revolut Stock (dividends and stock sales)

## How to Use

### 1. Access the CSV Import Page

Navigate to: **http://localhost:8081/ui/csv-import**

Or use the menu: **Import CSV** (in the navigation bar)

### 2. Create a Manual Account

1. Click **"+ Create New Account"**
2. Fill in the form:
   - **Bank Type**: Select the bank (Raiffeisen, Revolut CZK, etc.)
   - **Account Name**: Any name you want (e.g., "My Raiffeisen Checking")
   - **Currency**: Select the currency (CZK, EUR, USD, etc.)
   - **IBAN** (optional): Account IBAN if you have it
   - **Initial Balance** (optional): Starting balance before first transaction
3. Click **"Create Account"**

### 3. Upload CSV File

1. Select the account from the dropdown
2. Click **"Upload CSV"** or drag-and-drop a file
3. The system will:
   - Auto-detect the bank type
   - Show a preview of the first 5 rows
   - Count total transactions found

### 4. Review and Import

1. Review the preview to ensure the data looks correct
2. Click **"Import Transactions"**
3. The system will:
   - Parse all transactions
   - Check for duplicates (by amount, date, description, counterparty)
   - Skip duplicates automatically
   - Auto-categorize transactions
   - Store import history

### 5. View Results

- Import history shows:
  - Number of new transactions imported
  - Number of duplicates skipped
  - Any errors encountered
  - Timestamp of import

## Features

✅ **Auto-Detection**: System automatically detects which bank the CSV is from
✅ **Encoding Support**: Handles UTF-8, Windows-1250, ISO-8859-1, CP1252
✅ **Deduplication**: Prevents duplicate transactions from being imported twice
✅ **Auto-Categorization**: Transactions are automatically categorized based on description
✅ **Error Handling**: Detailed error messages for problematic rows
✅ **Import History**: Track all imports and re-import if needed
✅ **Multi-Import**: Import multiple CSV files to the same account

## CSV File Requirements

- **File encoding**: Must be UTF-8 or Windows-1250 (auto-detected)
- **First row**: Must contain column headers
- **Date columns**: Dates must be in the expected format for the bank
- **Amount columns**: Must contain numeric values (comma or dot decimal)
- **File size**: Recommended max 50MB per file

## Troubleshooting

### "Could not detect bank type"
- Verify the CSV file is from one of the supported banks
- Check that column headers match the expected format
- Try exporting the CSV again from your bank

### "No transactions found"
- Ensure the CSV contains data rows (not just headers)
- Check that dates are in the correct format
- Verify amount columns contain valid numbers

### "Duplicate transactions"
- This is normal if you re-import the same CSV file
- The system automatically skips duplicates
- Use the import history to see what was imported

### Encoding issues
- If special characters appear garbled, the file may be in a different encoding
- Try converting the file to UTF-8 before importing
- Contact support if the issue persists

## API Endpoints

For developers, the CSV import feature exposes the following REST API endpoints:

### Create Manual Account
```
POST /imports/accounts
Content-Type: application/x-www-form-urlencoded

account_type=Raiffeisen main
account_name=My Checking Account
currency=CZK
```

### Upload and Preview CSV
```
POST /imports/accounts/{account_id}/preview
Content-Type: multipart/form-data

file: <binary CSV file>
```

### Get Import History
```
GET /imports/accounts/{account_id}/history
```

### Delete Import Batch
```
DELETE /imports/accounts/{account_id}/imports/{batch_id}
```

## Example Workflow

1. Export CSV from Raiffeisenbank online banking
2. Visit http://localhost:8081/ui/csv-import
3. Create account "Raiffeisenbank Checking"
4. Upload the CSV file
5. Review the preview (332 transactions found)
6. Click "Import"
7. See results: 328 new, 4 duplicates, 0 errors
8. Transactions appear in the Transactions view with auto-categories

## Data Privacy

- CSV files are processed in memory and not stored on disk
- Transactions are encrypted in the database
- No bank credentials are stored or transmitted
- All import data stays within your local WealthTracker instance

## Next Steps

- View your imported transactions: **Transactions** → Filter by account
- Review categories: **Categories** → Edit auto-categories if needed
- Generate reports: **Reports** → See spending patterns for imported data
- Export data: **Export** → CSV, Excel (includes imported transactions)
