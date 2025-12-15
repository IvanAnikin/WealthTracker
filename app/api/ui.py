"""UI routes for web interface."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/ui", tags=["Web UI"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Accounts page."""
    return templates.TemplateResponse("accounts.html", {"request": request})


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(request: Request):
    """Transactions page."""
    return templates.TemplateResponse("transactions.html", {"request": request})


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Reports page."""
    return templates.TemplateResponse("reports.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/banks/connect", response_class=HTMLResponse)
async def banks_connect_page(request: Request):
    """Bank connection page."""
    return templates.TemplateResponse("banks_connect.html", {"request": request})


@router.get("/banks/callback", response_class=HTMLResponse)
async def banks_callback_page(request: Request):
    """Bank connection callback page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
