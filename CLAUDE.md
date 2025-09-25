# CLAUDE.md

# QuickExpense

A modern FastAPI application for **Canadian small businesses and sole proprietors** to process and submit expenses directly into **QuickBooks Online** using Python 3.12 with full type safety, modern development practices, and **Canadian tax compliance** (CRA ITA Section 67.1, GST/HST).

## Current Implementation Status

The application has been successfully restructured with:
- Modern Python 3.12 with full type hints
- FastAPI with async/await support
- Pydantic v2 for data validation
- Service-oriented architecture
- Dependency injection pattern
- Comprehensive test structure
- All pre-commit hooks passing
- **Complete CLI interface for receipt processing**
- **QuickBooks Purchase API integration fixed**
- **Vendor-aware business rules engine with hotel-specific categorization**

## Design Principles

- **Modern Python**: Python 3.12 with full [PEP 484/561 type hints](https://peps.python.org/pep-0484/), validated by [Pyright] and [mypy].
- **Explicit Contracts**: [Pydantic v2] models govern request and response schemas.
- **Service‑oriented**: Business logic resides in `services/`, API layer remains thin.
- **Stateless**: No database. Each session/expense is defined by request scope.
- **Developer Discipline**:
  - Dependencies managed via [uv].
  - Code correctness via [Ruff] with ALL rules enabled (600+ rules).
  - Pre-commit gates for type-checking, linting, formatting, and commit style.
  - [Black] formatter for consistent code style.
  - [Conventional Commits] specification for history clarity.

## Project Layout

```
quickexpense/
├── pyproject.toml          # Project metadata, dependencies (uv)
├── uv.lock                 # Locked dependencies
├── .ruff.toml             # Linting configuration (strictest)
├── .pre-commit-config.yaml # Pre-commit hooks
├── pyrightconfig.json     # Type checking configuration
├── src/
│   └── quickexpense/
│       ├── __init__.py
│       ├── main.py        # FastAPI app with lifespan events
│       ├── api/
│       │   ├── __init__.py
│       │   ├── health.py  # Health check endpoints
│       │   └── routes.py  # API endpoint definitions
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py      # Pydantic settings
│       │   └── dependencies.py # Dependency injection
│       ├── models/
│       │   ├── __init__.py
│       │   └── expense.py # Pydantic v2 models
│       └── services/
│           ├── __init__.py
│           └── quickbooks.py # QuickBooks client & service
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures
│   ├── unit/
│   │   ├── test_models.py
│   │   └── test_health.py
│   └── integration/
└── (legacy files - to be removed)
    ├── main.py
    ├── models.py
    ├── quickbooks_client.py
    └── oauth_setup.py
```

## Key Implementation Details

### Application Bootstrap

The QuickBooks client is initialized on app startup using FastAPI's lifespan events:

```python
@asynccontextmanager
async def lifespan(app: FastAPIType) -> AsyncGenerator[None, None]:
    settings = get_settings()
    qb_client = QuickBooksClient(
        base_url=settings.qb_base_url,
        company_id=settings.qb_company_id,
        access_token=settings.qb_access_token,
    )
    set_quickbooks_client(qb_client)
    yield
    await qb_client.close()
```

### Dependency Injection

Services are accessed via dependency injection:

```python
@router.post("/expenses")
async def create_expense(
    expense: Expense,
    service: QuickBooksServiceDep,  # Injected dependency
) -> dict[str, Any]:
    result = await service.create_expense(expense)
    return {"status": "success", "data": result}
```

### Models with Validation

Pydantic v2 models with proper Decimal handling:

```python
class Expense(BaseModel):
    vendor_name: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    date: date
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v
```

## Development Workflow

### Initial Setup
```bash
# Clone and install dependencies
git clone <repo>
cd quickExpense
uv sync

# Set up pre-commit hooks
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

### Environment Configuration


Create `.env` file with static configuration only:
```env
# QuickBooks OAuth Configuration (Static Settings)
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_REDIRECT_URI=http://localhost:8000/callback

# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT=30
```

**Note:** OAuth tokens (access_token, refresh_token) and company_id are now stored in `data/tokens.json` after running the OAuth flow.

### OAuth Setup (Required First Time)
```bash
# Set OAuth credentials as environment variables
export QB_CLIENT_ID="your_client_id"
export QB_CLIENT_SECRET="your_client_secret"

# Run OAuth connection script
uv run python scripts/connect_quickbooks_cli.py
```

This will:
1. Open a browser for QuickBooks authorization
2. Capture OAuth tokens after authorization
3. Save tokens to `data/tokens.json`

### Using the CLI
```bash
# First-time authentication
uv run quickexpense auth

# Check system status
uv run quickexpense status

# Process a receipt (images or PDFs)
uv run quickexpense upload receipt.jpg
uv run quickexpense upload receipt.pdf  # PDF support
uv run quickexpense upload receipt.jpg --dry-run  # Preview only
uv run quickexpense upload receipt.jpg --output json  # JSON output
```

### Running the API Server
```bash
# Development mode (with auto-reload)
uv run fastapi dev src/quickexpense/main.py

# Production mode
uv run uvicorn src.quickexpense.main:app --host 0.0.0.0 --port 8000
```

The application will:
- Load tokens from `data/tokens.json` on startup
- Automatically refresh tokens before they expire
- Save updated tokens back to `data/tokens.json`

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/unit/test_models.py
```

### Code Quality
```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Run specific checks
uv run ruff check src tests
uv run black src tests
uv run pyright
uv run mypy src tests
```

## CLI Commands

### Authentication and Status
- `quickexpense auth [--force]` - Authenticate with QuickBooks
- `quickexpense status` - Check system status and connections

### Receipt Processing
- `quickexpense upload <file> [--dry-run] [--output json]` - Process receipt and create expense
- `quickexpense --version` - Show version
- `quickexpense --help` - Show help

### Expense Verification
- `python scripts/verify_expense.py <purchase_id>` - Verify specific expense by ID
- `python scripts/search_vendor_expenses.py <vendor>` - Find expenses by vendor
- `python scripts/list_recent_expenses.py [days]` - List recent expenses

## API Endpoints

### Health Checks
- `GET /health` - Basic health check
- `GET /ready` - Readiness check with dependencies

### Expense Management
- `GET /api/v1/` - API information
- `POST /api/v1/expenses` - Create expense in QuickBooks
- `GET /api/v1/vendors/{vendor_name}` - Search for vendor
- `POST /api/v1/vendors?vendor_name=...` - Create vendor
- `GET /api/v1/accounts/expense` - List expense accounts
- `GET /api/v1/test-connection` - Test QuickBooks connection



### Example CLI Usage
```bash
# Process receipt with CLI
uv run quickexpense upload /path/to/receipt.jpg

# Output:
# Extracting data from receipt: receipt.jpg
# Creating expense in QuickBooks...
# Successfully created expense in QuickBooks (ID: 184)

# Verify the expense was created
uv run python scripts/verify_expense.py 184

# Output:
# ✅ Found Purchase ID: 184
#    Date: 2019-12-20
#    Vendor: Harrods
#    Total: $153.95
#    Payment Account: Chequing
```

### Example API Usage
```bash
# Create an expense via API
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "2024-01-15",
    "currency": "USD",
    "category": "Office Supplies",
    "tax_amount": 3.42
  }'

# Extract receipt data using Gemini AI
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "<base64_encoded_image_data>",
    "category": "Travel",
    "additional_context": "Business trip to NYC"
  }'
```

## Code Quality Standards

### Pre-commit Hooks
All code must pass:
- **Black** - Code formatting
- **Ruff** - Linting with ALL rules enabled (except explicitly ignored)
- **Pyright** - Strict type checking
- **mypy** - Additional type checking
- **Conventional Commits** - Commit message format

### Type Safety
- Full type annotations required (enforced by ANN rules)
- `Any` type only allowed where necessary (Pydantic validators)
- Strict pyright and mypy configurations

### Ignored Rules
Minimal, justified ignores:
- `D` - Docstrings (handled separately)
- `ANN101/102` - Type annotations for self/cls
- `TRY300` - Consider else block (not always clearer)
- `EM101/102` - Exception string literals
- `S608` - SQL injection (we control inputs)

## Gemini AI Receipt Processing

### Quick Setup

1. Get API Key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Add to `.env`: `GEMINI_API_KEY=your_actual_key`
3. Test with curl:

```bash
# Convert image to base64
base64 -i receipt.jpg > receipt.b64

# Send to API
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$(cat receipt.b64)\",
    \"category\": \"Travel\"
  }"
```

### Response
```json
{
  "receipt": { "vendor_name": "...", "total_amount": "..." },
  "expense_data": { "ready for QuickBooks" },
  "processing_time": 2.34
}
```

**Supported**: JPEG, PNG, GIF, BMP, WEBP, PDF

## Token Storage Architecture

### Single-User Prototype Design
For simplicity in prototyping, tokens are stored in a local JSON file:

- **Static Config** (`.env`): CLIENT_ID, CLIENT_SECRET, API URLs
- **Dynamic Tokens** (`data/tokens.json`): access_token, refresh_token, company_id

#### Token File Structure
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "x_refresh_token_expires_in": 8640000,
  "token_type": "bearer",
  "company_id": "...",
  "created_at": "2024-01-15T10:00:00Z",
  "saved_at": "2024-01-15T10:00:00Z"
}
```

### Token Flow
1. **Initial Setup**: Run `connect_quickbooks_cli.py` → saves to `data/tokens.json`
2. **App Startup**: Loads tokens from JSON file
3. **Token Refresh**: OAuth manager refreshes → callback saves to JSON
4. **Manual Update**: Use `scripts/update_tokens.py` if needed

## Recent Improvements

1. ✅ **CLI Implementation**: Complete command-line interface with auth, status, and upload commands
2. ✅ **QuickBooks Purchase Fix**: Fixed "Invalid account type" error by adding AccountRef field
3. ✅ **Payment Account Support**: Added bank and credit card account selection
4. ✅ **Enhanced Error Handling**: Clear user messages for authentication errors
5. ✅ **Field Mapping Fix**: Corrected receipt-to-expense field mappings
6. ✅ **Vendor-Aware Business Rules (PRE-115)**: Enhanced business rules engine with vendor context awareness for Canadian tax compliance
   - Hotel marketing fees now correctly categorized as Travel-Lodging (not Professional Services)
   - Vendor-specific rules take precedence over generic rules when vendor patterns match
   - Enhanced confidence scoring based on vendor-category alignment
   - Comprehensive validation and warning system for potential mismatches
   - Backward compatible with existing categorization rules
   - CRA ITA Section 67.1 compliance for meals & entertainment (50% deductible)
   - GST/HST Input Tax Credit proper handling
7. ✅ **Structured Logging (PRE-117)**: Professional audit trail system for CRA compliance
   - JSON structured logs with correlation ID tracking
   - 7-year retention policy for business records
   - Sensitive data sanitization with performance preservation
   - Entity-aware logging with T2125 tax form context
   - Integration with CLI for verbose audit mode

## Business Rules Configuration

### Vendor-Aware Business Rules
The business rules engine now supports vendor context awareness, enabling more accurate categorization based on vendor type:

```json
{
  "id": "hotel_marketing_fees",
  "priority": 110,  // Higher priority than generic rules
  "name": "Hotel Marketing and Service Fees",
  "conditions": {
    "description_keywords": ["marketing fee", "resort fee", "destination fee"],
    "vendor_patterns": ["*hotel*", "*marriott*", "*hilton*", "*courtyard*"]
  },
  "actions": {
    "category": "Travel-Lodging",
    "qb_account": "Travel - Lodging",
    "confidence_boost": 0.2
  }
}
```

**Key Features:**
- Vendor-specific rules take precedence over generic rules
- Confidence scoring adjusts based on vendor-category alignment
- Validation warnings for potential vendor-category mismatches
- Backward compatible with existing single-category rules

**Example:** Marketing fees from hotels are now correctly categorized as Travel-Lodging instead of Professional Services, based on vendor context.

## Next Steps

1. ~~**Remove Legacy Files**: Delete old files in root directory~~ ✓
2. ~~**Add OAuth Flow**: Implement proper OAuth2 flow for token refresh~~ ✓
3. ~~**CLI Interface**: Add command-line interface for receipt processing~~ ✓
4. ~~**Vendor-Aware Business Rules**: Enhanced categorization with vendor context~~ ✓
5. ✅ **Add Logging**: Structured logging with appropriate levels
6. **Add More Tests**: Increase coverage to >90%
7. **API Documentation**: Enhance OpenAPI/Swagger docs
8. **Rate Limiting**: Add rate limiting for API endpoints
9. **Monitoring**: Add OpenTelemetry instrumentation
10. **Batch Processing**: Add support for multiple receipt uploads
11. ✅ **PDF Support**: Add PDF receipt extraction capability

## Commit Discipline

Use [Conventional Commits]:
- `feat: add expense submission endpoint`
- `fix: correct currency validation`
- `chore: update ruff config`


[uv]: https://github.com/astral-sh/uv
[Ruff]: https://docs.astral.sh/ruff/
[Black]: https://github.com/psf/black
[Pyright]: https://github.com/microsoft/pyright
[mypy]: https://mypy-lang.org/
[Pydantic v2]: https://docs.pydantic.dev/latest/
[Conventional Commits]: https://www.conventionalcommits.org/
