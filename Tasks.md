# Project Task List
## Personal Finance Aggregator (Python, Open Banking)

## PHASE 0 — Project Initialization

### 0.1 Define Project Parameters

- [ ] Confirm single-user vs multi-user support (default: multi-user)
- [ ] Confirm target countries/banks (default: CZ – KB, RB, Revolut)
- [ ] Confirm MVP feature set (as per Tech Spec)

### 0.2 Repository Setup

- [ ] Create Git repository
- [ ] Define branch strategy (main / dev)
- [ ] Add .gitignore (Python, Docker, env files)
- [ ] Add README with project overview

## PHASE 1 — Development Environment

### 1.1 Python & Tooling

- [ ] Initialize Python 3.11 virtual environment
- [ ] Define dependency manager (pip + requirements.txt or Poetry)
- [ ] Add core dependencies:
  - fastapi
  - uvicorn
  - sqlalchemy
  - alembic
  - pydantic
  - psycopg2 / asyncpg
  - python-dotenv
  - passlib (bcrypt/argon2)
  - httpx
  - apscheduler

### 1.2 Docker Setup

- [ ] Create Dockerfile for API
- [ ] Create docker-compose.yml:
  - API
  - PostgreSQL
- [ ] Configure environment variables

## PHASE 2 — Backend Skeleton

### 2.1 FastAPI App Structure

- [ ] Create app factory
- [ ] Configure middleware (CORS, sessions)
- [ ] Add healthcheck endpoint (/health)
- [ ] Setup logging

### 2.2 Configuration Management

- [ ] Create settings module (Pydantic BaseSettings)
- [ ] Load secrets from environment
- [ ] Separate dev/prod config

## PHASE 3 — Database & Models

### 3.1 Database Initialization

- [ ] Initialize SQLAlchemy engine
- [ ] Configure session management
- [ ] Integrate Alembic

### 3.2 Core Models

- [ ] User model
- [ ] Institution model
- [ ] Requisition (consent) model
- [ ] Account model
- [ ] Transaction model
- [ ] Category model
- [ ] Categorization rule model

### 3.3 Migrations

- [ ] Generate initial Alembic migration
- [ ] Apply migration to dev DB

## PHASE 4 — Authentication & Security

### 4.1 Authentication

- [ ] User registration endpoint
- [ ] Login endpoint
- [ ] Logout endpoint
- [ ] Password hashing (bcrypt/argon2)
- [ ] Session or JWT handling

### 4.2 Authorization

- [ ] Protect authenticated routes
- [ ] Role handling (user/admin)

### 4.3 Security Hardening

- [ ] CSRF protection
- [ ] Secure cookie settings
- [ ] Input validation
- [ ] Rate limiting (optional MVP+)

## PHASE 5 — Open Banking Provider Integration

### 5.1 Provider Abstraction

- [ ] Define BankProviderClient interface
- [ ] Implement mock provider for testing

### 5.2 GoCardless (Nordigen) Client

- [ ] Register application with provider
- [ ] Implement authentication (API key/token)
- [ ] Implement institution listing
- [ ] Implement requisition creation
- [ ] Implement account retrieval
- [ ] Implement balance retrieval
- [ ] Implement transaction retrieval

### 5.3 Consent Lifecycle

- [ ] Store requisition status
- [ ] Handle expired/revoked consents
- [ ] Allow user-initiated disconnect

## PHASE 6 — Bank Connection Flow

### 6.1 Connect Flow

- [ ] Endpoint: list institutions
- [ ] Endpoint: create requisition
- [ ] Redirect user to bank SCA
- [ ] Callback handler
- [ ] Persist linked accounts

### 6.2 Error Handling

- [ ] Handle user cancelation
- [ ] Handle failed SCA
- [ ] Display consent status in UI

## PHASE 7 — Data Synchronization

### 7.1 Sync Engine

- [ ] Manual sync endpoint
- [ ] Scheduled sync job (APScheduler)
- [ ] Fetch balances
- [ ] Fetch transactions

### 7.2 Data Normalization

- [ ] Normalize transaction amounts (signs)
- [ ] Normalize currencies
- [ ] Map provider payload → internal model

### 7.3 Deduplication

- [ ] Implement external_id logic
- [ ] Implement hash fallback
- [ ] Enforce DB uniqueness constraints

## PHASE 8 — Balance Computation Logic

### 8.1 Initial Balance Handling

- [ ] Capture initial booked balance
- [ ] Store initial balance date

### 8.2 Balance-at-Date Service

- [ ] Implement balance calculation function
- [ ] Support arbitrary date input
- [ ] Exclude pending transactions by default

### 8.3 Aggregations

- [ ] Per-account balance
- [ ] Total balance across accounts

## PHASE 9 — Categorization & Rules

### 9.1 Categories

- [ ] CRUD for categories
- [ ] Parent/child support

### 9.2 Rules Engine

- [ ] Create rule model
- [ ] Implement rule matching (regex / contains)
- [ ] Apply rules on import
- [ ] Allow manual override

## PHASE 10 — Reporting

### 10.1 Cashflow

- [ ] Monthly aggregation
- [ ] Income vs expenses
- [ ] Per-account filtering

### 10.2 Category Reports

- [ ] Totals per category
- [ ] Time range filtering

## PHASE 11 — Export

### 11.1 CSV Export

- [ ] Transactions export
- [ ] Cashflow export
- [ ] Category summary export

### 11.2 Performance

- [ ] Streaming responses
- [ ] Date filtering

## PHASE 12 — Web UI

### 12.1 Layout

- [ ] Base layout template
- [ ] Navigation
- [ ] Auth pages

### 12.2 Core Screens

- [ ] Dashboard
- [ ] Accounts list
- [ ] Transactions table
- [ ] Reports view
- [ ] Settings (banks, rules)

### 12.3 UX Constraints

- [ ] No bank credentials in UI
- [ ] Explicit consent visibility

## PHASE 13 — Testing

### 13.1 Unit Tests

- [ ] Balance computation
- [ ] Rule matching
- [ ] Deduplication

### 13.2 Integration Tests

- [ ] Mock provider sync
- [ ] Full connect → sync → report flow

## PHASE 14 — Deployment & Ops

### 14.1 Production Readiness

- [ ] Environment separation
- [ ] Secure secrets handling
- [ ] DB backups

### 14.2 Monitoring

- [ ] Logging
- [ ] Health checks
- [ ] Error reporting

## PHASE 15 — Documentation

### 15.1 Developer Docs

- [ ] Architecture overview
- [ ] Setup instructions
- [ ] Environment variables list

### 15.2 User Docs

- [ ] Bank connection explanation
- [ ] Privacy & security notes

## Final Output Definition

Project is considered MVP-complete when:

- [ ] A user can connect a bank
- [ ] Transactions are synced
- [ ] Balance can be computed for any date
- [ ] Reports and CSV export work
- [ ] No bank credentials are ever handled
