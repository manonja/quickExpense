# QuickExpense

Modern expense management API that automatically creates QuickBooks expenses from receipts using AI-powered extraction and robust OAuth token management.

## Features

- 🤖 **AI Receipt Processing** - Extract expense data from receipt images using Google Gemini
- 🔄 **Automatic Token Management** - Never worry about expired tokens
- 📊 **Direct QuickBooks Integration** - Create vendors and expenses seamlessly
- 🚀 **Modern Python Stack** - FastAPI, Pydantic v2, Python 3.12+

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- QuickBooks Developer Account
- Google Gemini API key (for receipt processing)

## Quick Start

### 1. Clone & Install

```bash
git clone <repository>
cd quickExpense
uv sync
```

### 2. Configure QuickBooks OAuth

```bash
# Set your QuickBooks credentials
export QB_CLIENT_ID="your_client_id"
export QB_CLIENT_SECRET="your_client_secret"

# Run the OAuth connection tool
uv run python scripts/connect_quickbooks_cli.py
```

This opens a browser to connect your QuickBooks account and saves tokens to `.env`.

### 3. Configure Gemini (Optional)

Add to your `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key
```

### 4. Run the Application

```bash
# Development mode with auto-reload
uv run fastapi dev src/quickexpense/main.py

# Production mode
uv run uvicorn src.quickexpense.main:app --host 0.0.0.0 --port 8000
```

## API Usage

### Test Connection
```bash
curl http://localhost:8000/api/v1/test-connection
```

### Create Expense
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "2024-01-15",
    "category": "Office Supplies",
    "tax_amount": 3.42
  }'
```

### Extract Receipt (AI-Powered)
```bash
# Convert image to base64
base64 -i receipt.jpg > receipt.b64

# Extract expense data
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$(cat receipt.b64)\",
    \"category\": \"Office Supplies\"
  }"
```

## Project Structure

```
quickExpense/
├── src/quickexpense/
│   ├── api/           # API endpoints
│   ├── core/          # Configuration & dependencies
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic & integrations
│   └── main.py        # FastAPI app entry point
├── scripts/
│   └── connect_quickbooks_cli.py  # OAuth setup tool
├── tests/             # Test suite
├── pyproject.toml     # Project dependencies
└── .env              # Environment variables (created by OAuth tool)
```

## Key Features Explained

### Automatic Token Refresh
- Access tokens auto-refresh before expiry (5-min buffer)
- Background task checks token validity every minute
- Handles QuickBooks refresh token rotation
- Zero downtime from token expiration

### Receipt Processing
- Supports JPEG, PNG, GIF, BMP, WEBP formats
- Extracts vendor, amount, date, tax information
- Returns QuickBooks-ready expense data

### Environment Variables

Required:
```env
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_COMPANY_ID=your_company_id        # Set by OAuth tool
QB_ACCESS_TOKEN=your_access_token    # Set by OAuth tool
QB_REFRESH_TOKEN=your_refresh_token  # Set by OAuth tool
GEMINI_API_KEY=your_gemini_key       # For receipt extraction
```

Optional:
```env
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com  # Default
QB_TOKEN_REFRESH_BUFFER=300  # Seconds before expiry to refresh
DEBUG=false                  # Enable debug logging
```

## Development

### Run Tests
```bash
uv run pytest
uv run pytest --cov  # With coverage
```

### Code Quality
```bash
# All checks
uv run pre-commit run --all-files

# Individual checks
uv run ruff check src tests
uv run mypy src tests
uv run black src tests
```

### Pre-commit Hooks
```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "401 Unauthorized" | Tokens expired - run `uv run python scripts/connect_quickbooks_cli.py` |
| "Module not found" | Run `uv sync` to install dependencies |
| "Connection failed" | Check QB credentials and company ID in `.env` |
| Token refresh fails | Ensure refresh token hasn't expired (100 days) |

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/` | GET | API info |
| `/api/v1/test-connection` | GET | Test QuickBooks connection |
| `/api/v1/expenses` | POST | Create expense |
| `/api/v1/vendors/{name}` | GET | Search vendor |
| `/api/v1/vendors` | POST | Create vendor |
| `/api/v1/accounts/expense` | GET | List expense accounts |
| `/api/v1/receipts/extract` | POST | Extract receipt data (AI) |

## License

[Your License]
