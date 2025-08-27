"""QuickBooks integration service."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from quickexpense.models import Expense

logger = logging.getLogger(__name__)


class QuickBooksError(Exception):
    """Base exception for QuickBooks operations."""


class QuickBooksClient:
    """HTTP client for QuickBooks API."""

    def __init__(
        self,
        base_url: str,
        company_id: str,
        access_token: str,
        timeout: float = 30.0,
    ) -> None:
        """Initialize QuickBooks client."""
        self.base_url = base_url
        self.company_id = company_id
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=f"{base_url}/v3/company/{company_id}",
            headers=self.headers,
            timeout=timeout,
        )

    async def __aenter__(self) -> QuickBooksClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to QuickBooks API."""
        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=json,
                params=params,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPStatusError as e:
            logger.error("QuickBooks API error: %s", e.response.text)
            raise QuickBooksError(f"API request failed: {e}") from e
        except httpx.RequestError as e:
            logger.error("Request error: %s", e)
            raise QuickBooksError(f"Request failed: {e}") from e

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, **kwargs)

    async def test_connection(self) -> dict[str, Any]:
        """Test the connection to QuickBooks API."""
        return await self.get(f"companyinfo/{self.company_id}")


class VendorSearchResult(BaseModel):
    """Vendor search result model."""

    id: str
    display_name: str
    active: bool = True


class AccountInfo(BaseModel):
    """Account information model."""

    id: str
    name: str
    account_type: str
    active: bool = True


class QuickBooksService:
    """Service for QuickBooks operations."""

    def __init__(self, client: QuickBooksClient) -> None:
        """Initialize the service with a QuickBooks client."""
        self.client = client

    async def test_connection(self) -> dict[str, Any]:
        """Test QuickBooks connection."""
        return await self.client.test_connection()

    async def search_vendor(self, vendor_name: str) -> list[VendorSearchResult]:
        """Search for a vendor by name."""
        query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}'"
        response = await self.client.get("query", params={"query": query})

        vendors = response.get("QueryResponse", {}).get("Vendor", [])
        return [
            VendorSearchResult(
                id=v["Id"],
                display_name=v.get("DisplayName", ""),
                active=v.get("Active", True),
            )
            for v in vendors
        ]

    async def create_vendor(self, vendor_name: str) -> VendorSearchResult:
        """Create a new vendor."""
        data = {"DisplayName": vendor_name, "Active": True}
        response = await self.client.post("vendor", json=data)

        return VendorSearchResult(
            id=response["Vendor"]["Id"],
            display_name=response["Vendor"]["DisplayName"],
            active=response["Vendor"].get("Active", True),
        )

    async def get_expense_accounts(self) -> list[AccountInfo]:
        """Get all expense accounts."""
        query = "SELECT * FROM Account WHERE AccountType = 'Expense' AND Active = true"
        response = await self.client.get("query", params={"query": query})

        accounts = response.get("QueryResponse", {}).get("Account", [])
        return [
            AccountInfo(
                id=a["Id"],
                name=a["Name"],
                account_type=a["AccountType"],
                active=a.get("Active", True),
            )
            for a in accounts
        ]

    async def create_expense(self, expense: Expense) -> dict[str, Any]:
        """Create an expense in QuickBooks."""
        # Search or create vendor
        vendors = await self.search_vendor(expense.vendor_name)
        if not vendors:
            vendor = await self.create_vendor(expense.vendor_name)
            vendor_id = vendor.id
        else:
            vendor_id = vendors[0].id

        # Get expense accounts
        accounts = await self.get_expense_accounts()
        if not accounts:
            raise QuickBooksError("No expense accounts found")

        # Find matching account or use first
        account = next(
            (a for a in accounts if expense.category.lower() in a.name.lower()),
            accounts[0],
        )

        # Build purchase data
        purchase_data = self._build_purchase_data(
            expense=expense,
            vendor_id=vendor_id,
            vendor_name=expense.vendor_name,
            account_id=account.id,
            account_name=account.name,
        )

        return await self.client.post("purchase", json=purchase_data)

    def _build_purchase_data(
        self,
        *,
        expense: Expense,
        vendor_id: str,
        vendor_name: str,
        account_id: str,
        account_name: str,
    ) -> dict[str, Any]:
        """Build purchase data for QuickBooks API."""
        base_amount = expense.amount - expense.tax_amount
        line_items = [
            {
                "Amount": float(base_amount),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": account_id, "name": account_name}
                },
                "Description": expense.category,
            }
        ]

        # Add tax line if applicable
        if expense.tax_amount > Decimal("0"):
            line_items.append(
                {
                    "Amount": float(expense.tax_amount),
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": account_id, "name": "Sales Tax"}
                    },
                    "Description": "Tax",
                }
            )

        return {
            "PaymentType": "Cash",
            "EntityRef": {"value": vendor_id, "name": vendor_name},
            "TotalAmt": float(expense.amount),
            "TxnDate": expense.date.isoformat(),
            "CurrencyRef": {"value": expense.currency},
            "Line": line_items,
        }
