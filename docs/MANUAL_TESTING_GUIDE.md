# QuickExpense Manual Testing Guide

This guide walks through manual testing of the QuickExpense application to verify all functionality works correctly after the OAuth implementation.

## Prerequisites

1. Ensure you have a `.env` file configured (copy from `.env.example`)
2. QuickBooks Developer account with sandbox credentials
3. (Optional) Google Gemini API key for receipt extraction

## 1. Initial Setup

### Step 1.1: Install Dependencies
```bash
cd quickExpense
uv sync
```

### Step 1.2: Set Up OAuth Credentials
```bash
# Set your QuickBooks OAuth credentials
export QB_CLIENT_ID="your_client_id"
export QB_CLIENT_SECRET="your_client_secret"

# Run OAuth setup
uv run python scripts/connect_quickbooks_cli.py
```
This will:
- Open a browser for QuickBooks authorization
- Capture the OAuth tokens
- Save them to `.env`

### Step 1.3: Start the Application
```bash
# Development mode with auto-reload
uv run fastapi dev src/quickexpense/main.py

# Or production mode
uv run uvicorn src.quickexpense.main:app --host 0.0.0.0 --port 8000
```

## 2. Health Check Tests

### Test 2.1: Basic Health Check
```bash
curl http://localhost:8000/health
```
Expected: `{"status": "ok"}`

### Test 2.2: Readiness Check
```bash
curl http://localhost:8000/ready
```
Expected: `{"status": "ready", "dependencies": {"quickbooks": "connected"}}`

## 3. QuickBooks Connection Tests

### Test 3.1: Test Connection
```bash
curl http://localhost:8000/api/v1/test-connection
```
Expected: Company information JSON

### Test 3.2: List Expense Accounts
```bash
curl http://localhost:8000/api/v1/accounts/expense
```
Expected: Array of expense accounts

## 4. Vendor Management Tests

### Test 4.1: Search for Vendor
```bash
curl "http://localhost:8000/api/v1/vendors/Office%20Depot"
```
Expected: Array of matching vendors (may be empty)

### Test 4.2: Create Vendor
```bash
curl -X POST "http://localhost:8000/api/v1/vendors?vendor_name=Test%20Vendor%20$(date +%s)"
```
Expected: Created vendor details with ID

## 5. Expense Creation Tests

### Test 5.1: Create Basic Expense
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "'$(date +%Y-%m-%d)'",
    "currency": "USD",
    "category": "Office Supplies",
    "tax_amount": 3.42
  }'
```
Expected: Success response with QuickBooks Purchase ID

### Test 5.2: Create Expense with New Vendor
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "New Test Vendor '$(date +%s)'",
    "amount": 100.00,
    "date": "'$(date +%Y-%m-%d)'",
    "category": "Travel",
    "tax_amount": 0,
    "description": "Manual test expense"
  }'
```
Expected: Success (vendor created automatically)

## 6. Receipt Extraction Tests (Optional)

### Test 6.1: Extract Receipt Data
First, create a test image:
```bash
# Create a simple test image (1x1 white pixel)
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" > test_image.b64
```

Then test extraction:
```bash
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$(cat test_image.b64)\",
    \"category\": \"Office Supplies\"
  }"
```
Expected: Extracted receipt data (if Gemini API key configured)

## 7. OAuth Token Tests

### Test 7.1: Check Token Status
```bash
uv run python scripts/test_oauth_refresh.py
```
This shows current token status and expiry times.

### Test 7.2: Monitor Auto-Refresh
```bash
# Run in a separate terminal to monitor token refresh
uv run python scripts/test_oauth_refresh.py monitor
```
Leave running to observe automatic token refresh behavior.

### Test 7.3: Force Token Expiry
To test 401 handling and retry:
1. Manually edit `.env` and change `QB_ACCESS_TOKEN` to an invalid value
2. Try creating an expense
3. The system should handle the 401 and refresh the token automatically

## 8. Run Integration Test Suite

### Test 8.1: Full Integration Test
```bash
uv run python scripts/test_integration.py
```
This runs through all major endpoints automatically.

## 9. Load Testing (Optional)

### Test 9.1: Concurrent Requests
```bash
# Install hey (HTTP load generator)
brew install hey  # macOS
# or
sudo apt-get install hey  # Ubuntu

# Test with 10 concurrent requests
hey -n 100 -c 10 http://localhost:8000/api/v1/test-connection
```

## 10. Error Scenarios

### Test 10.1: Invalid Expense Data
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "",
    "amount": -100,
    "date": "invalid-date"
  }'
```
Expected: Validation error with details

### Test 10.2: Expired Tokens
1. Wait for access token to expire (1 hour)
2. Or manually expire by editing `.env`
3. Make any API call
4. Should automatically refresh and retry

## Troubleshooting

### Common Issues

1. **"401 Unauthorized"**
   - Run `uv run python scripts/connect_quickbooks_cli.py` to refresh tokens
   - Check `.env` has valid tokens

2. **"Company ID not found"**
   - Ensure `QB_COMPANY_ID` is set in `.env`
   - Should be set automatically by OAuth script

3. **"Connection refused"**
   - Ensure the server is running
   - Check the port (default: 8000)

4. **Receipt extraction fails**
   - Verify `GEMINI_API_KEY` is set and valid
   - Check the [Google AI Studio](https://aistudio.google.com/app/apikey)

### Viewing Logs

```bash
# Run with debug logging
DEBUG=true uv run fastapi dev src/quickexpense/main.py

# Or set in .env
echo "DEBUG=true" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
```

## Next Steps

After manual testing:
1. Check QuickBooks Sandbox to verify created expenses
2. Review the OAuth token refresh logs
3. Test with production credentials (update `QB_BASE_URL` in `.env`)
