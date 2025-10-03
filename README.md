# QuickExpense

Modern expense management system for **Canadian small businesses and sole proprietors** with a powerful CLI and API that automatically creates QuickBooks expenses from receipts using AI-powered extraction and robust OAuth token management with **Canadian tax compliance** (CRA ITA Section 67.1, GST/HST).

## Features

- **Modern Web UI** - Clean, professional interface with essentials-only grid design
- **CLI Interface** - Simple commands for receipt processing and expense management
- **AI Receipt Processing** - Extract expense data from receipt images using Google Gemini
- **Multi-Agent System** - Three specialized agents ensure accuracy with confidence scoring
- **Hybrid LLM Approach** - Gemini for images (HEIC/PDF), TogetherAI for cost-effective reasoning
- **Automatic Token Management** - Never worry about expired tokens
- **Direct QuickBooks Integration** - Create vendors and expenses seamlessly
- **Modern Python Stack** - FastAPI, Pydantic v2, Python 3.12+ with strictest type safety
- **Smart Account Mapping** - Automatically selects appropriate payment and expense accounts
- **Structured Audit Logging** - Professional CRA-compliant audit trail with 7-year retention
- **Canadian Tax Compliance** - Business rules engine with CRA-compliant categorization
  - Hotel marketing fees → Travel-Lodging (not Professional Services)
  - Meals & Entertainment → 50% deductible (CRA ITA Section 67.1)
  - GST/HST → 100% Input Tax Credit eligible
  - Tourism levies → 100% deductible travel expenses

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- QuickBooks Developer Account
- Google Gemini API key (for image processing)
- TogetherAI API key (optional, for multi-agent reasoning)

## Quick Start

### 1. Clone & Install

```bash
git clone <repository>
cd quickExpense
uv sync
```

### 2. Configure Environment

Create a `.env` file with:
```env
# QuickBooks OAuth
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_REDIRECT_URI=http://localhost:8000/callback
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com

# Gemini AI (for image processing)
GEMINI_API_KEY=your_gemini_api_key

# TogetherAI (optional, for multi-agent reasoning)
TOGETHER_API_KEY=your_together_api_key
LLM_PROVIDER=together  # Options: together, gemini, auto
```

### 3. Authenticate with QuickBooks

```bash
# Run OAuth authentication
uv run quickexpense auth

# Verify connection
uv run quickexpense status
```

### 4. Process Your First Receipt

**Option A: Web UI (Recommended)**
```bash
# Start the web server
uv run fastapi dev src/quickexpense/main.py

# Open browser to http://localhost:8000
# Click "Connect to QuickBooks" if needed
# Drag and drop receipt file or click to upload
```

**Option B: CLI**
```bash
# Process a receipt and create expense in QuickBooks
uv run quickexpense upload receipt.jpg

# Preview without creating expense
uv run quickexpense upload receipt.jpg --dry-run
```

## Usage

### CLI Commands

```bash
# Show help
uv run quickexpense --help

# Authenticate with QuickBooks
uv run quickexpense auth [--force]

# Check system status
uv run quickexpense status

# Upload and process receipt
uv run quickexpense upload <receipt-file> [--dry-run] [--output json]
```

### Web UI

Access the modern web interface at `http://localhost:8000` after starting the server.

**Features:**
- **Three-column essentials grid**: Receipt info, Tax analysis, Status
- **Drag & drop upload**: Support for JPEG, PNG, PDF, HEIC files
- **Real-time processing**: Visual feedback with progress indicators
- **Expandable details**: Optional advanced information section
- **Responsive design**: Works on mobile and desktop
- **Dry run mode**: Preview processing without creating expenses

### Supported Receipt Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- WebP (.webp)
- PDF (.pdf)
- HEIC (.heic, .heif) - iPhone photos

### Example Output
```
$ uv run quickexpense upload receipt.jpg

Extracting data from receipt: receipt.jpg
Creating expense in QuickBooks...

=== Receipt Data ===
Vendor: Office Depot
Date: 2024-01-15
Total Amount: $45.99
Tax: $3.42

=== Result ===
Successfully created expense in QuickBooks (ID: 123)
```

### Verifying Expenses Were Created

After uploading a receipt, you can verify the expense was created in QuickBooks:

#### 1. QuickBooks Online Interface
- Log into [QuickBooks Sandbox](https://sandbox.qbo.intuit.com/)
- Go to **Expenses** → **Expenses** to see your new expense

#### 2. CLI Verification Tools
```bash
# Verify a specific expense by Purchase ID
uv run python scripts/verify_expense.py 123

# Search expenses by vendor name
uv run python scripts/search_vendor_expenses.py "Office Depot"

# List recent expenses
uv run python scripts/list_recent_expenses.py
```

#### Example Verification Output
```
$ uv run python scripts/verify_expense.py 185

✅ Found Purchase ID: 185
   Date: 2019-12-20
   Vendor: Harrods
   Total: $153.95
   Payment Type: Cash
   Payment Account: Chequing

   Line Items:
   - $153.95 → Insurance Expense-General Liability Insurance
```

### API Usage (Alternative)

If you prefer the REST API:

```bash
# Start the API server
uv run fastapi dev src/quickexpense/main.py

# Create expense via API
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{"vendor_name": "Office Depot", "amount": 45.99, "date": "2024-01-15"}'
```

## Project Structure

```
quickExpense/
├── src/quickexpense/
│   ├── api/           # API endpoints
│   │   ├── routes.py     # Core API endpoints
│   │   └── web_endpoints.py # Web UI endpoints
│   ├── core/          # Configuration & dependencies
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic & integrations
│   ├── web/           # Web UI files
│   │   ├── templates/    # HTML templates
│   │   └── static/       # CSS, JavaScript
│   ├── cli.py         # CLI interface
│   └── main.py        # FastAPI app entry point
├── data/
│   └── tokens.json    # OAuth tokens (gitignored)
├── scripts/           # Utility scripts
├── tests/             # Test suite
├── pyproject.toml     # Project dependencies
└── .env              # Environment variables
```

## Key Features Explained

### Web UI Features
- **Essentials-only design**: Focus on Receipt, Tax Analysis, and Status
- **Grid-based layout**: Efficient use of horizontal space
- **Responsive design**: Works on mobile and desktop devices
- **Real-time processing**: Visual feedback and progress indicators
- **Expandable details**: Optional advanced information section
- **Drag & drop upload**: Intuitive file upload experience
- **OAuth integration**: Seamless QuickBooks authentication with popup flow

### CLI Features
- Simple command-line interface for all operations
- Built-in authentication flow with browser integration
- Real-time status checking and connection validation
- Dry-run mode for testing without creating expenses
- JSON output option for integration with other tools

### Automatic Token Refresh
- Access tokens auto-refresh before expiry (5-min buffer)
- Automatic retry on 401 errors with token refresh
- Handles QuickBooks refresh token rotation
- Zero downtime from token expiration

### Receipt Processing
- Supports JPEG, PNG, GIF, BMP, WEBP, PDF formats
- AI-powered extraction of vendor, amount, date, tax
- Automatic vendor creation if not found
- Smart expense account categorization
- Automatic payment account selection (bank/credit card)

### Expense Verification
- Built-in verification scripts to confirm expenses in QuickBooks
- Search by vendor, date, or Purchase ID
- View expense details including account mappings

### Environment Variables

Required in `.env`:
```env
# QuickBooks OAuth Configuration
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_REDIRECT_URI=http://localhost:8000/callback
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com

# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_key

# TogetherAI Configuration (optional)
TOGETHER_API_KEY=your_together_key
LLM_PROVIDER=together
```

Tokens are stored separately in `data/tokens.json` after authentication.

## Development

### Run Tests
```bash
uv run pytest
uv run pytest --cov  # With coverage
```

### Code Quality
```bash
# All checks (ALL Ruff rules enabled - strictest possible)
uv run pre-commit run --all-files

# Individual checks
uv run ruff check src tests  # 600+ rules enabled
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
| "401 Unauthorized" | Tokens expired - run `uv run quickexpense auth --force` |
| "No authentication tokens found" | Run `uv run quickexpense auth` |
| "Invalid account type" | Fixed! The CLI now properly handles payment accounts |
| "Module not found" | Run `uv sync` to install dependencies |
| "Connection failed" | Check credentials in `.env` and run `quickexpense status` |
| Token refresh fails | Run `uv run quickexpense auth --force` for new tokens |

## CLI Reference

| Command | Description | Example |
|---------|-------------|---------|
| `quickexpense auth` | Authenticate with QuickBooks | `quickexpense auth --force` |
| `quickexpense status` | Check system status | `quickexpense status` |
| `quickexpense upload` | Process receipt & create expense | `quickexpense upload receipt.jpg` |
| `quickexpense --version` | Show version | `quickexpense --version` |
| `quickexpense --help` | Show help | `quickexpense --help` |

## API Reference

For REST API usage, start the server with `uv run fastapi dev src/quickexpense/main.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI home page |
| `/api/v1/` | GET | API info |
| `/api/v1/test-connection` | GET | Test QuickBooks connection |
| `/api/v1/expenses` | POST | Create expense |
| `/api/v1/vendors/{name}` | GET | Search vendor |
| `/api/v1/vendors` | POST | Create vendor |
| `/api/v1/accounts/expense` | GET | List expense accounts |
| `/api/v1/receipts/extract` | POST | Extract receipt data (AI) |
| `/api/v1/receipts/extract-with-agents` | POST | Process with multi-agent system |
| `/api/web/auth-status` | GET | Check QuickBooks authentication |
| `/api/web/upload-receipt` | POST | Upload receipt via web UI |

## License

[Your License]
