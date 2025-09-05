# QuickStart Testing Guide

## Prerequisites
- QuickBooks Developer account with sandbox company
- OAuth app created in QuickBooks with redirect URI: `http://localhost:8000/api/quickbooks/callback`

## Step 1: OAuth Setup (One-time)

```bash
# Make sure your .env file has:
# QB_CLIENT_ID=your_client_id_here
# QB_CLIENT_SECRET=your_client_secret_here

# Run OAuth connection (it reads from .env automatically)
uv run python scripts/connect_quickbooks_cli.py
```

This will:
1. Open browser for QuickBooks login
2. Ask you to select a company (use sandbox)
3. Save tokens to `data/tokens.json`

## Step 2: Start the API Server

```bash
# In a new terminal
uv run fastapi dev src/quickexpense/main.py
```

Wait for: "Application startup complete"

## Step 3: Test with CURL

### 3.1 Quick Health Check
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`

### 3.2 Test QuickBooks Connection
```bash
curl http://localhost:8000/api/v1/test-connection
```
Expected: Company information JSON

### 3.3 Create a Vendor
```bash
curl -X POST "http://localhost:8000/api/v1/vendors?vendor_name=Acme%20Corp%20$(date +%s)"
```
Save the vendor name for the next step!

### 3.4 Create an Expense
```bash
# Replace VENDOR_NAME with the vendor you just created
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "VENDOR_NAME",
    "amount": 99.99,
    "date": "'$(date +%Y-%m-%d)'",
    "currency": "USD",
    "category": "Office Supplies",
    "tax_amount": 8.50,
    "description": "Test expense from QuickExpense"
  }'
```

## Step 4: Verify in QuickBooks

1. Log into your QuickBooks sandbox
2. Go to Expenses → Expenses
3. You should see your new expense!

## Automated Test Script

Run all tests at once:
```bash
./test_quickbooks_api.sh
```

## Troubleshooting

- **401 Unauthorized**: Tokens expired, run OAuth setup again
- **Company ID not found**: Check `data/tokens.json` has `company_id`
- **Vendor not found**: The vendor name must match exactly
