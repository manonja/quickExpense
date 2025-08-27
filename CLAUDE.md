# claude.md

# QuickExpense

A modern FastAPI application for processing and submitting expenses directly into **QuickBooks Online** using a command-line workflow.
The design emphasizes stateless request handling, strict typing, modern Python (3.12), and clean service-oriented architecture.


## Design Principles

- **Modern Python**: Python 3.12 with full [PEP 484/561 type hints](https://peps.python.org/pep-0484/), validated by [Pyright].
- **Explicit Contracts**: [Pydantic v2] models govern request and response schemas.
- **Service‑oriented**: Business logic resides in `services/`, API layer remains thin.
- **Stateless**: No database. Each session/expense is defined by request scope.
- **Developer Discipline**:
  - Dependencies managed via [uv].
  - Code correctness via [Ruff] (strictest rules).
  - Pre-commit gates for type-checking, linting, commit style.
  - [Conventional Commits] specification for history clarity.


## Project Layout

```
quickexpense/
├── pyproject.toml        # Project metadata, dependencies
├── uv.lock               # uv lockfile for reproducible builds
├── .pre-commit-config.yaml
├── .ruff.toml
├── src/
│   └── quickexpense/
│       ├── __init__.py
│       ├── main.py          # FastAPI entrypoint
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py    # API endpoint definitions
│       ├── models/
│       │   ├── __init__.py
│       │   └── expense.py   # Pydantic models for expenses
│       ├── services/
│       │   ├── __init__.py
│       │   └── quickbooks.py  # Service for QuickBooks Online submission
│       └── cli/
│           ├── __init__.py
│           └── submit.py    # CLI interaction with FastAPI service

```


## Code Sketch

### `src/quickexpense/models/expense.py`

```
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal

class Expense(BaseModel):
    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    date: date
    category: str
    vendor: str
```

### `src/quickexpense/services/quickbooks.py`

```
from . import exceptions
from ..models.expense import Expense

class QuickBooksService:
    def __init__(self, client):
        self.client = client  # Placeholder for QuickBooks SDK / HTTP client

    async def submit_expense(self, expense: Expense) -> dict:
        # Transform model → QuickBooks payload
        payload = {
            "Line": [
                {
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Amount": float(expense.amount),
                    "Description": expense.description,
                }
            ],
            "VendorRef": {"name": expense.vendor},
            "CurrencyRef": {"value": expense.currency},
            "TxnDate": expense.date.isoformat(),
        }

        try:
            return await self.client.post("/v3/company/expenses", json=payload)
        except Exception as e:
            raise exceptions.QuickBooksSubmissionError(str(e))
```

### `src/quickexpense/api/routes.py`

```
from fastapi import APIRouter
from ..models.expense import Expense
from ..services.quickbooks import QuickBooksService

router = APIRouter()

@router.post("/expenses")
async def submit_expense(expense: Expense) -> dict:
    service = QuickBooksService(client=None)  # Replace with real client
    return await service.submit_expense(expense)
```

### `src/quickexpense/main.py`

```
from fastapi import FastAPI
from .api import routes

app = FastAPI(title="QuickExpense")
app.include_router(routes.router)
```


## Tooling

### Dependency Management

- [uv]: Fast, modern dependency and environment manager.
  ```
  uv init --src src quickexpense
  uv add fastapi pydantic[dotenv] typer httpx
  uv add --dev ruff pyright pre-commit
  ```

### Ruff Configuration (`.ruff.toml`)

```
[tool.ruff]
select = ["ALL"]
ignore = ["D"]  # optionally ignore docstring warnings
line-length = 88
target-version = "py312"
```

### Pre-commit Hooks (`.pre-commit-config.yaml`)

```
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
  - repo: https://github.com/pre-commit/mirrors-pyright
    rev: v1.1.362
    hooks:
      - id: pyright
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.1.0
    hooks:
      - id: conventional-pre-commit
```


## Development

```
# Install dependencies
uv sync

# Run API locally
uv run fastapi dev src/quickexpense/main.py

# Run lint + type-check
uv run ruff check src
uv run pyright

# Run hooks manually
pre-commit run --all-files
```


## Commit Discipline

Use [Conventional Commits]:
- `feat: add expense submission endpoint`
- `fix: correct currency validation`
- `chore: update ruff config`



[uv]: https://github.com/astral-sh/uv
[Ruff]: https://docs.astral.sh/ruff/
[Pyright]: https://github.com/microsoft/pyright
[Pydantic v2]: https://docs.pydantic.dev/latest/
[Conventional Commits]: https://www.conventionalcommits.org/
