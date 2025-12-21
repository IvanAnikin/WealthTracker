# TrueLayer Setup Guide

This guide will help you configure TrueLayer as your Open Banking provider for WealthTracker.

## Prerequisites

- TrueLayer Console account (https://console.truelayer.com/)
- Application created in TrueLayer Console
- Client ID and Client Secret obtained

## Step 1: Get Your Credentials

1. Log in to [TrueLayer Console](https://console.truelayer.com/)
2. Go to your application settings
3. Find your credentials:
   - **Client ID** (e.g., `sandbox-client-12345`)
   - **Client Secret** (e.g., `abcd1234-5678-90ef-...`)

## Step 2: Configure Redirect URI

In TrueLayer Console, add your callback URL:
```
http://localhost:8081/banks/connect/callback
```

For production, use your actual domain:
```
https://yourdomain.com/banks/connect/callback
```

## Step 3: Update .env File

Open `/Users/ivananikin/Documents/WealthTracker/.env` and update:

```bash
# TrueLayer Configuration
TRUELAYER_CLIENT_ID=your-actual-client-id-here
TRUELAYER_CLIENT_SECRET=your-actual-client-secret-here
TRUELAYER_BASE_URL=https://api.truelayer.com
TRUELAYER_AUTH_URL=https://auth.truelayer.com
```

**For Sandbox/Testing:**
Use the sandbox URLs:
```bash
TRUELAYER_BASE_URL=https://api.truelayer-sandbox.com
TRUELAYER_AUTH_URL=https://auth.truelayer-sandbox.com
```

## Step 4: Restart the Server

```bash
./venv/bin/python -m uvicorn app.main:app --reload --port 8081
```

## Step 5: Test the Integration

1. Open http://localhost:8081/ui/
2. Log in or register
3. Click "Connect Bank"
4. Select a country
5. Choose a bank from the list
6. You'll be redirected to TrueLayer's auth flow
7. Complete the bank authorization
8. You'll be redirected back with connected accounts

## API Endpoints

TrueLayer provider implements all standard endpoints:

- `GET /banks/institutions?country=GB` - List banks by country
- `POST /banks/connect` - Initiate connection
- `GET /banks/accounts` - List connected accounts
- `GET /transactions` - Retrieve transactions
- `POST /sync` - Sync account data

## Supported Countries

TrueLayer supports various countries. Check the [Supported Providers](https://console.truelayer.com/providers) page for the full list.

Common country codes:
- GB - United Kingdom
- IE - Ireland
- ES - Spain
- FR - France
- DE - Germany
- IT - Italy
- LT - Lithuania
- PL - Poland

## Troubleshooting

### 401 Unauthorized
- Check your Client ID and Client Secret are correct
- Ensure you're using the right environment (sandbox vs production)
- Verify credentials are not expired

### No institutions returned
- Check the country code is supported
- Verify API credentials are valid
- Try with sandbox environment first

### Redirect URI mismatch
- Ensure the redirect URI in `.env` matches what's configured in TrueLayer Console
- Check protocol (http vs https)
- Verify port number matches

## Switching from GoCardless

The application automatically uses TrueLayer if credentials are configured. No code changes needed!

Priority order:
1. TrueLayer (if `TRUELAYER_CLIENT_ID` is set)
2. GoCardless (if `GOCARDLESS_SECRET_ID` is set)
3. Mock provider (if no credentials)

## Additional Resources

- [TrueLayer Documentation](https://docs.truelayer.com/)
- [TrueLayer Data API](https://docs.truelayer.com/docs/data-api-basics)
- [Console](https://console.truelayer.com/)
- [API Reference](https://docs.truelayer.com/reference)
