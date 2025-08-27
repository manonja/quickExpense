# QuickExpense

A modern FastAPI application for processing and submitting expenses directly into QuickBooks Online using Python 3.12 with full type safety and modern development practices.

## 🚀 Features

- **Modern Python**: Built with Python 3.12 using type hints throughout
- **FastAPI**: High-performance async API with automatic documentation
- **Pydantic v2**: Robust data validation and serialization
- **Type Safety**: Enforced with pyright and mypy in strict mode
- **Code Quality**: Ruff with strictest settings for linting and formatting
- **Dependency Management**: Using uv for fast, reliable package management
- **Testing**: Comprehensive test suite with pytest
- **QuickBooks Integration**: Full OAuth2 flow and expense creation

## 📋 Prerequisites

- Python 3.12+
- uv (install with `pip install uv`)
- QuickBooks Developer Account
- QuickBooks Sandbox Company

## 🛠 Installation

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd quickExpense

# Install dependencies using uv
uv sync
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
QB_CLIENT_ID=your_client_id_here
QB_CLIENT_SECRET=your_client_secret_here
QB_REDIRECT_URI=http://localhost:8000/callback
QB_COMPANY_ID=your_company_id
QB_ACCESS_TOKEN=your_access_token
QB_REFRESH_TOKEN=your_refresh_token
```

### 3. Set Up Pre-commit Hooks

```bash
# Install pre-commit hooks
uv run pre-commit install
```

## 🏃‍♂️ Running the Application

### Development Mode (with auto-reload)

```bash
uv run fastapi dev src/quickexpense/main.py
```

### Production Mode

```bash
uv run uvicorn src.quickexpense.main:app --host 0.0.0.0 --port 8000
```

## 🧪 Testing

### Run All Tests

```bash
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov
```

### Run Specific Tests

```bash
uv run pytest tests/unit/test_models.py
```

## 📡 API Endpoints

### Health Check

```bash
# Check service health
curl http://localhost:8000/health

# Check service readiness
curl http://localhost:8000/ready
```

### Expense Management

```bash
# Create an expense
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

# Search for a vendor
curl http://localhost:8000/api/v1/vendors/Office%20Depot

# Create a vendor
curl -X POST "http://localhost:8000/api/v1/vendors?vendor_name=New%20Vendor"

# Get expense accounts
curl http://localhost:8000/api/v1/accounts/expense

# Test QuickBooks connection
curl http://localhost:8000/api/v1/test-connection
```

## 🏗 Project Structure

```
quickexpense/
├── pyproject.toml          # Project metadata and dependencies
├── uv.lock                 # Locked dependencies
├── .ruff.toml             # Ruff configuration
├── .pre-commit-config.yaml # Pre-commit hooks
├── pyrightconfig.json     # Type checking configuration
├── src/
│   └── quickexpense/
│       ├── __init__.py
│       ├── main.py        # FastAPI application entry point
│       ├── api/
│       │   ├── __init__.py
│       │   ├── health.py  # Health check endpoints
│       │   └── routes.py  # Main API routes
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py      # Settings management
│       │   └── dependencies.py # Dependency injection
│       ├── models/
│       │   ├── __init__.py
│       │   └── expense.py # Pydantic models
│       └── services/
│           ├── __init__.py
│           └── quickbooks.py # QuickBooks service layer
└── tests/
    ├── __init__.py
    ├── conftest.py        # Pytest fixtures
    ├── unit/
    │   ├── __init__.py
    │   ├── test_models.py
    │   └── test_health.py
    └── integration/
        └── __init__.py
```

## 🔧 Development

### Adding Dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a development dependency
uv add --dev package-name
```

### Code Quality

```bash
# Run linting
uv run ruff check src tests

# Run formatting
uv run ruff format src tests

# Run type checking
uv run pyright
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

- **Ruff**: Linting and formatting
- **Pyright**: Type checking
- **Mypy**: Additional type checking
- **Conventional Commits**: Commit message format

### Commit Convention

Follow conventional commits specification:

```bash
feat: add new expense category support
fix: correct tax calculation logic
docs: update API documentation
test: add unit tests for expense model
chore: update dependencies
```

## 🐳 Docker Support (Optional)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src ./src

# Install dependencies
RUN uv sync --no-dev

# Run the application
CMD ["uv", "run", "uvicorn", "src.quickexpense.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🔒 Security

- All QuickBooks credentials are stored in environment variables
- OAuth2 tokens should be refreshed regularly
- Never commit `.env` files or credentials to version control

## 📚 API Documentation

Once the application is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Ensure all tests pass
4. Run pre-commit hooks
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details
