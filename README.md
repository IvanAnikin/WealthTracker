# WealthTracker

A secure, Python-based web application that aggregates bank accounts via PSD2 Open Banking (read-only), syncs transactions, computes historical balances, and provides cashflow and spending insights with exportable reports.

## Features

### MVP Features (Current Implementation)

- ✅ **User Authentication** - Secure registration and JWT-based login
- ✅ **Open Banking Integration** - Connect to banks via GoCardless (Nordigen) or mock provider
- ✅ **Bank Connection Management** - List institutions, create requisitions, manage consents
- ✅ **Transaction Synchronization** - Manual and scheduled sync with deduplication
- ✅ **Balance Computation** - Calculate historical balances at any date
- ✅ **Transaction Categorization** - Manual and rule-based auto-categorization
- ✅ **Financial Reports** - Monthly cashflow, category breakdown, spending trends
- ✅ **Data Export** - CSV export of transactions and reports
- ✅ **RESTful API** - Complete API with FastAPI and automatic OpenAPI docs

## Architecture

```
FastAPI Backend (Python 3.11+)
    ↓
SQLAlchemy ORM + Alembic Migrations
    ↓
PostgreSQL (prod) / SQLite (dev)
    ↓
GoCardless Bank Account Data API (Open Banking)
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: PostgreSQL (production), SQLite (development)
- **ORM**: SQLAlchemy 2.x with Alembic migrations
- **Authentication**: JWT with bcrypt password hashing
- **Open Banking**: GoCardless Bank Account Data (formerly Nordigen)
- **Scheduling**: APScheduler (for periodic sync)
- **Deployment**: Docker + Docker Compose

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip or uv for package management
- PostgreSQL (for production) or SQLite (for development)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd WealthTracker
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ./venv/bin/python -m pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your SECRET_KEY and other configuration
   ```

5. **Initialize database**
   ```bash
   ./venv/bin/python -m  alembic upgrade head
   alembic upgrade head
   ```

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ./venv/bin/python -m uvicorn app.main:app --reload --port 8081
   ```

7. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

### Using Docker

1. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Run migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

3. **Access the application**
   - API: http://localhost:8000

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get JWT token
- `POST /auth/logout` - Logout
- `GET /auth/me` - Get current user info

### Bank Connection
- `GET /banks/institutions` - List available banks
- `POST /banks/connect` - Initiate bank connection
- `GET /banks/connect/callback` - Handle connection callback
- `GET /banks/requisitions` - List user's requisitions
- `DELETE /banks/requisitions/{id}` - Disconnect bank
- `GET /banks/accounts` - List user's accounts

### Synchronization
- `POST /sync` - Manually sync accounts
- `POST /sync/background` - Trigger background sync

### Transactions
- `GET /transactions` - List transactions (with filters)
- `GET /transactions/{id}` - Get specific transaction
- `GET /transactions/balances/current` - Get current balances
- `GET /transactions/balances/net` - Get net balance

### Categories
- `GET /categories` - List categories
- `POST /categories` - Create category
- `PUT /categories/{id}` - Update category
- `DELETE /categories/{id}` - Delete category
- `POST /categories/transactions/{id}/categorize` - Assign category to transaction
- `POST /categories/auto-categorize` - Auto-categorize transactions
- `GET /categories/rules` - List categorization rules
- `POST /categories/rules` - Create rule
- `DELETE /categories/rules/{id}` - Delete rule

### Reports
- `GET /reports/cashflow` - Monthly cashflow report
- `GET /reports/categories` - Category breakdown
- `GET /reports/trends` - Spending trends
- `GET /reports/accounts` - Account summary
- `GET /reports/statistics` - Transaction statistics

### Export
- `GET /export/transactions.csv` - Export transactions to CSV
- `GET /export/cashflow.csv` - Export cashflow report to CSV
- `GET /export/categories.csv` - Export category breakdown to CSV

## Configuration

Key environment variables:

```bash
# Application
APP_NAME=WealthTracker
DEBUG=False
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///./wealth_tracker.db
# For PostgreSQL: postgresql://user:password@localhost:5432/wealthtracker

# Open Banking (GoCardless/Nordigen)
GOCARDLESS_SECRET_ID=your-secret-id
GOCARDLESS_SECRET_KEY=your-secret-key
# Leave empty to use mock provider for testing

# Session
SESSION_SECRET_KEY=your-session-key
SESSION_MAX_AGE=86400

# CORS
CORS_ORIGINS=["http://localhost:8000"]

# Logging
LOG_LEVEL=INFO
```

## Security Features

- ✅ JWT-based authentication
- ✅ Bcrypt password hashing
- ✅ HTTPS-only in production
- ✅ Secure cookie settings
- ✅ CORS protection
- ✅ No bank credentials stored or processed
- ✅ All bank access via secure Open Banking aggregator

## Balance Calculation

The system uses a precise algorithm to calculate balances at any historical date:

```
balance(date) = initial_balance 
              + SUM(booked_transactions.amount)
              WHERE booking_date > initial_balance_date
              AND booking_date <= date
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black app/
ruff check app/
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Project Structure

```
WealthTracker/
├── app/
│   ├── api/              # API endpoints
│   │   ├── auth.py
│   │   ├── banks.py
│   │   ├── sync.py
│   │   ├── transactions.py
│   │   ├── categories.py
│   │   ├── reports.py
│   │   └── export.py
│   ├── core/             # Core configuration
│   │   ├── config.py
│   │   └── security.py
│   ├── db/               # Database configuration
│   │   └── session.py
│   ├── models/           # SQLAlchemy models
│   │   └── __init__.py
│   ├── schemas/          # Pydantic schemas
│   │   └── __init__.py
│   ├── services/         # Business logic
│   │   ├── bank_provider.py
│   │   ├── balance_service.py
│   │   ├── sync_service.py
│   │   ├── categorization_service.py
│   │   └── report_service.py
│   └── main.py          # FastAPI application
├── alembic/             # Database migrations
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose setup
├── alembic.ini        # Alembic configuration
└── .env               # Environment variables
```

## Roadmap

See [Tasks.md](Tasks.md) for detailed implementation progress.

### Future Enhancements (Post-MVP)
- Web UI with dashboard, charts, and visualizations
- Real-time transaction notifications
- Multi-currency support with conversion
- Budget tracking and alerts
- Advanced ML-based categorization
- Mobile app
- Bank statement file import (OFX, CSV)
- Financial goals and projections

## Contributing

This is a personal project, but contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [Technical Specification](Technical_Specification.md) for architecture details
- Review the [Tasks](Tasks.md) for implementation progress

## Acknowledgments

- Built with FastAPI
- Open Banking integration via GoCardless Bank Account Data
- Following PSD2 AIS regulations

## Scripts

- `scripts/analyze_income_db.py`: DB-level income analysis across all data. Groups by account, account type, institution, counterparty, and description keywords. Useful to see overall income sources.
   - Run: `./venv/bin/python scripts/analyze_income_db.py`

- `scripts/analyze_income_db_excluding_internal.py`: Same as above but excludes internal transfers (`Transaction.is_internal_transfer = True`) to reveal true external income sources.
   - Run: `./venv/bin/python scripts/analyze_income_db_excluding_internal.py`

- `scripts/analyze_income_categories.py`: API-based analysis using `/reports/categories` for the last 180 days. Shows category breakdown for the authenticated user.
   - Run: `./venv/bin/python scripts/analyze_income_categories.py`

- `scripts/analyze_income_categories_excluding_internal.py`: API analysis of `/reports/categories` with `exclude_internal_transfers=true`. Surfaces income categories excluding internal transfers.
   - Run: `./venv/bin/python scripts/analyze_income_categories_excluding_internal.py`

Notes:
- API scripts create a temporary user automatically and require the API server running (e.g., `./venv/bin/python -m uvicorn app.main:app --reload --port 8081`). They analyze only data associated with the logged-in user.
- DB scripts read directly from the configured database and reflect the complete dataset in your environment.


'''
ivananikin@mac001-hol-anik-2 WealthTracker % ./venv/bin/python scripts/analyze_income_db.py
Income transactions in DB: 1001

=== Top income by category ===
Uncategorized                             count= 728  amount=1,800,847.94
Subscriptions                             count=  91  amount=196,498.00
Salary                                    count=  31  amount=189,222.00
Transfers                                 count= 151  amount=187,494.03

=== Top income by institution ===
MANUAL_CSV                                count=1001  amount=2,374,061.97

=== Top income by account_type ===
Revolut CZK                               count= 648  amount=1,704,301.50
Komerční Banka main                       count=  62  amount=390,649.00
Raiffeisen main                           count=  39  amount=220,382.60
Revolut EUR                               count=  40  amount=39,477.79
Revolut USD                               count=  23  amount=15,680.76
Revolut Crypto CZK                        count= 140  amount=1,897.72
Revolut Crypto USD                        count=  36  amount=1,035.59
Revolut Stock USD                         count=   7  amount=536.56
Revolut Stock EUR                         count=   6  amount=100.45

=== Top income by account ===
Revolut CZK [manual_csv_342eaafd-3753-41  count= 648  amount=1,704,301.50
Komerční Banka main [manual_csv_55d238be  count=  62  amount=390,649.00
Raiffeisen main [manual_csv_28341133-3aa  count=  39  amount=220,382.60
Revolut EUR [manual_csv_3e58ca1c-18ed-40  count=  40  amount=39,477.79
Revolut USD [manual_csv_3a77cf35-4df6-48  count=  23  amount=15,680.76
Revolut Crypto CZK [manual_csv_217aa85e-  count= 140  amount=1,897.72
Revolut Crypto USD [manual_csv_83825dbc-  count=  36  amount=1,035.59
Revolut Stock USD [manual_csv_821b77c7-7  count=   7  amount=536.56
Revolut Stock EUR [manual_csv_efdf538b-0  count=   6  amount=100.45

=== Top income by counterparty ===
<none>                                    count= 711  amount=1,759,460.05
CZ1520100000002901431712                  count=  11  amount=133,750.00
Ekaterina Anikina                         count=  23  amount=117,000.00
NN Zivotni pojistovn                      count=   2  amount=113,860.00
Ivan Sergejevič Anik                      count=   7  amount=59,222.00
UK-FAKULTA SOCIÁLNÍCH VĚD                 count=   9  amount=56,100.00
ANIKIN IVAN SERGEJEV                      count=   5  amount=22,110.00
CZ5430300000002332930019                  count=  11  amount=19,781.00
CZ0420100000002800349859                  count=   2  amount=15,750.00
Anna Marková                              count=   1  amount=13,000.00

=== Top income by description_keywords ===
uncategorized                             count= 699  amount=2,184,392.40
transfer_in                               count= 151  amount=187,494.03
crypto_sale                               count= 147  amount=2,175.07
dividend                                  count=   4  amount=0.47
'''