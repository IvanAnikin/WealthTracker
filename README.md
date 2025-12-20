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
   alembic upgrade head
   ```

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload
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
