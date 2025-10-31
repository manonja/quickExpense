# QuickExpense

Modern expense management for **Canadian small businesses** with AI-powered receipt processing that automatically creates QuickBooks expenses with **CRA tax compliance** (ITA Section 67.1, GST/HST).

## What It Does

Snap a photo of your receipt → Get expense created in QuickBooks with proper tax categorization.

- 📸 **Receipt Processing**: Upload photos (JPEG, PNG, HEIC, PDF) via CLI or Web UI
- 🤖 **Multi-Agent AI**: 3 specialized agents extract data, apply CRA rules, validate taxes
- 📚 **QuickBooks Integration**: Auto-creates vendors and expenses with proper accounts
- 🇨🇦 **Tax Compliance**: Meals 50% deductible, GST/HST Input Tax Credits, hotel fees categorized correctly
- 🔐 **OAuth Management**: Auto-refreshing tokens, no manual intervention needed

## Quick Commands

```bash
# Authenticate with QuickBooks (first time)
uv run quickexpense auth

# Process a receipt via CLI
uv run quickexpense upload receipt.jpg

# Start web UI
uv run fastapi dev src/quickexpense/main.py
# → Open http://localhost:8000

# Test with API - Multi-agent processing (recommended)
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.pdf" \
  -F "additional_context=Business dinner with client"

# Test with Web UI endpoint - Agent mode
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.jpg" \
  -F "additional_context=Business dinner" \
  -F "dry_run=false"
```

## Tech Stack

- **Python 3.12+** with strict type safety (Pyright, mypy, Ruff 600+ rules)
- **FastAPI** for async web API and modern UI
- **Pydantic v2** for data validation
- **LLM Providers**:
  - **Gemini 2.0 Flash** (`gemini-2.0-flash-exp`) - Image processing (HEIC/PDF support)
  - **TogetherAI** (`meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo`) - Cost-effective reasoning (47% cheaper)
- **ag2 (AutoGen)** - Multi-agent orchestration
- **uv** - Fast dependency management

## Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** - Fast package manager
- **QuickBooks Developer Account** - Get at [developer.intuit.com](https://developer.intuit.com/)
- **Gemini API Key** - Get at [aistudio.google.com](https://aistudio.google.com/app/apikey)
- **TogetherAI API Key** (optional) - Get at [api.together.xyz](https://api.together.xyz/)

## Quick Start

### 1. Clone & Install

```bash
git clone <repository>
cd quickExpense
uv sync
```

### 2. Configure Environment

Create a `.env` file:
```env
# QuickBooks OAuth (required)
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_REDIRECT_URI=http://localhost:8000/callback
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com

# Gemini AI (required - for image processing)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-exp

# TogetherAI (optional - enables multi-agent system)
TOGETHER_API_KEY=your_together_api_key
TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
LLM_PROVIDER=together  # Options: together, gemini, auto

# HuggingFace Space Protection (optional - for public deployments)
ENABLE_PASSWORD_PROTECTION=false
HF_SPACE_PASSWORD=your_secure_password
```

**Note**: OAuth tokens (access_token, refresh_token, company_id) are stored in `data/tokens.json` after authentication.

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

### Web UI Features

Access at `http://localhost:8000` after starting the server.

- **Essentials-only grid**: Receipt | Tax Analysis | Status (three columns)
- **Drag & drop**: Upload JPEG, PNG, PDF, HEIC files
- **Real-time feedback**: Progress indicators and visual status
- **Expandable details**: Optional advanced information
- **Dry run mode**: Preview without creating expenses in QuickBooks
- **Agent mode toggle**: Switch between standard and multi-agent processing
  - Standard: Fast Gemini extraction + business rules
  - Agent: 2-agent system with CRA compliance (DataExtractionAgent + CRArulesAgent)

### Supported File Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| JPEG | `.jpg`, `.jpeg` | Standard photos |
| PNG | `.png` | Screenshots |
| PDF | `.pdf` | Multi-page receipts |
| HEIC | `.heic`, `.heif` | iPhone photos (native support) |
| Other | `.gif`, `.bmp`, `.webp` | Also supported |

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

### REST API Usage

```bash
# Start the API server
uv run fastapi dev src/quickexpense/main.py

# Process receipt with multi-agent system (recommended)
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.pdf" \
  -F "additional_context=Hotel stay for client meeting"

# Create expense directly (no AI processing)
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{"vendor_name": "Office Depot", "amount": 45.99, "date": "2024-01-15"}'
```

**Agent Processing Examples:**

```bash
# Process restaurant receipt with CRA compliance
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@restaurant_receipt.jpg" \
  -F "additional_context=Business lunch with client"

# Process hotel receipt with automatic lodging categorization
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@hotel_invoice.pdf" \
  -F "additional_context=Conference accommodation"

# Process office supply receipt
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@office_depot.png" \
  -F "additional_context=Office supplies for workspace"
```

**Agent Response Structure:**

The multi-agent endpoint returns comprehensive analysis including:
- **Receipt Data**: Vendor, date, amounts, line items
- **CRA Categorization**: Category, deductibility %, QuickBooks account
- **Tax Calculations**: GST/HST validation, deductible amounts
- **Confidence Scores**: Per-agent and overall confidence
- **Audit Risk**: Low/Medium/High risk assessment
- **Flags for Review**: Issues requiring manual verification

**Note:** The `additional_context` parameter helps the AI better understand and categorize your expense (e.g., "Business dinner with client", "Hotel for conference").

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

## How It Works

### Multi-Agent Processing Pipeline

When you upload a receipt, three specialized AI agents work in sequence:

1. **DataExtractionAgent** (Gemini)
   - Extracts vendor, date, amount, taxes from image/PDF
   - Handles HEIC, PDF, multi-page documents
   - Outputs structured JSON

2. **CRArulesAgent** (TogetherAI)
   - Applies Canadian tax rules (CRA ITA Section 67.1)
   - Categorizes expenses (Meals 50%, Travel, Office Supplies, etc.)
   - Determines GST/HST Input Tax Credit eligibility
   - Vendor-aware rules (hotel fees → Travel-Lodging)

3. **TaxCalculatorAgent** (TogetherAI)
   - Validates tax calculations
   - Confidence scoring and audit risk assessment
   - Final approval or flags for manual review

### Token Management

**One-time setup required**: Configure OAuth credentials in `.env` file (see step 2 above)

**After first authentication**: Tokens are automatically managed
- **Storage**: `data/tokens.json` (gitignored)
- **Auto-refresh**: 5-minute buffer before expiry
- **Retry logic**: Automatic 401 error handling
- **Zero downtime**: Handles QuickBooks token rotation seamlessly

You only need to run `quickexpense auth` once. The system handles all token refreshing automatically.

## Testing the Agents API with RAG

The multi-agent system uses RAG (Retrieval Augmented Generation) to incorporate CRA tax law documents for accurate categorization.

### Quick Test

```bash
# Test with a real receipt
uv run python scripts/test_agents_with_real_receipts.py \
  /Users/manonjacquin/Documents/receipts/marriot.pdf \
  "Hotel accommodation for business conference"
```

**What this tests:**
- ✅ RAG database with CRA tax law documents
- ✅ DataExtractionAgent (Gemini) - Extract receipt data
- ✅ CRArulesAgent (TogetherAI + RAG) - Apply Canadian tax rules

**Expected results:**
- Room charges → Travel-Lodging (100% deductible)
- Restaurant charges → Travel-Meals (50% deductible per ITA 67.1)
- GST/HST → Tax-GST/HST (100% ITC eligible)
- Tourism levies → Travel-Taxes (100% deductible)

**Documentation:**
- [TEST_AGENTS_RAG.md](TEST_AGENTS_RAG.md) - Detailed testing guide
- [AGENTS_VS_BASELINE_TEST_RESULTS.md](AGENTS_VS_BASELINE_TEST_RESULTS.md) - API comparison results with CLI commands

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

Start server: `uv run fastapi dev src/quickexpense/main.py`
API docs: http://localhost:8000/docs

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI home page |
| `/api/v1/receipts/process-file` | POST | **Process receipt with multi-agent AI** (recommended) |
| `/api/v1/expenses` | POST | Create expense directly (no AI) |
| `/api/v1/receipts/extract` | POST | Extract receipt data with Gemini only |
| `/api/v1/test-connection` | GET | Test QuickBooks connection |
| `/api/v1/vendors/{name}` | GET | Search vendor |
| `/api/v1/accounts/expense` | GET | List expense accounts |
| `/api/web/auth-status` | GET | Check QuickBooks authentication |
| `/api/web/upload-receipt` | POST | Upload receipt via web UI (standard mode) |
| `/api/web/upload-receipt-agents` | POST | Upload receipt via web UI (agent mode) |

### Multi-Agent Processing Endpoints

#### API Endpoint: `/api/v1/receipts/process-file`

**POST** `/api/v1/receipts/process-file`

Process receipts through the 2-agent system (DataExtractionAgent + CRArulesAgent) with full CRA compliance.

**Parameters:**
- `receipt` (file): Receipt file (JPEG, PNG, PDF, HEIC)
- `additional_context` (string, optional): Context to improve categorization

**Examples:**
```bash
# Restaurant receipt with meals & entertainment rules
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@restaurant.jpg" \
  -F "additional_context=Business lunch with client"

# Hotel invoice with automatic lodging categorization
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@marriott.pdf" \
  -F "additional_context=Hotel for business conference"

# Office supplies receipt
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@staples.png" \
  -F "additional_context=Office supplies for home office"
```

**Response Structure:**
```json
{
  "success": true,
  "overall_confidence": 0.92,
  "vendor_name": "Marriott Hotel",
  "total_amount": 250.00,
  "category": "Travel-Lodging",
  "deductibility_percentage": 100,
  "qb_account": "Travel - Lodging",
  "calculated_gst_hst": 12.50,
  "tax_validation_result": "valid",
  "audit_risk": "low",
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "success": true,
      "confidence_score": 0.95,
      "processing_time": 1.2
    },
    {
      "agent_name": "CRArulesAgent",
      "success": true,
      "confidence_score": 0.90,
      "processing_time": 0.8
    }
  ],
  "flags_for_review": []
}
```

#### Web UI Endpoint: `/api/web/upload-receipt-agents`

**POST** `/api/web/upload-receipt-agents`

Same agent processing optimized for the web UI with enhanced response format.

**Parameters:**
- `file` (file): Receipt file
- `additional_context` (string, optional): Business context
- `dry_run` (boolean, optional): Preview without creating QuickBooks expense

**Key Features:**
- Returns web-compatible response format
- Includes QuickBooks expense creation (unless dry_run=true)
- Enhanced UI display data with agent breakdown
- Compatible with web UI's agent mode toggle

**Example:**
```bash
# Dry run mode for preview
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.jpg" \
  -F "additional_context=Business dinner" \
  -F "dry_run=true"

# Create expense in QuickBooks
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.jpg" \
  -F "additional_context=Business dinner"
```

**Response:** Enhanced format with `agent_details`, `business_rules`, `tax_deductibility`, and `quickbooks` sections optimized for web UI display.

## HuggingFace Space Deployment

For public deployments, enable HTTP Basic Auth password protection:

```env
ENABLE_PASSWORD_PROTECTION=true
HF_SPACE_PASSWORD=your_secure_password
```

**Protected paths:** Main UI, API endpoints, uploads
**Exempt paths:** Health checks (`/health`, `/ready`), static files, docs

Users will see a browser login dialog. Username can be blank; password must match `HF_SPACE_PASSWORD`.

## License

MIT
