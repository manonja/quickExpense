"""QuickBooks integration service."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from quickexpense.models import Expense
    from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager

logger = logging.getLogger(__name__)


class QuickBooksError(Exception):
    """Base exception for QuickBooks operations."""


class QuickBooksClient:
    """HTTP client for QuickBooks API with OAuth support."""

    def __init__(
        self,
        base_url: str,
        company_id: str,
        access_token: str | None = None,
        timeout: float = 30.0,
        *,
        oauth_manager: QuickBooksOAuthManager | None = None,
    ) -> None:
        """Initialize QuickBooks client.

        Args:
            base_url: QuickBooks API base URL
            company_id: QuickBooks company ID
            access_token: Initial access token (if no oauth_manager)
            timeout: Request timeout in seconds
            oauth_manager: OAuth token manager for automatic refresh
        """
        self.base_url = base_url
        self.company_id = company_id
        self.timeout = timeout
        self.oauth_manager = oauth_manager

        # Set initial token
        if oauth_manager and oauth_manager.tokens:
            access_token = oauth_manager.tokens.access_token
        elif not access_token:
            msg = "Either access_token or oauth_manager with tokens required"
            raise ValueError(msg)

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

        # Register callback to update token
        if oauth_manager:
            oauth_manager.add_token_update_callback(self._update_access_token)

    async def __aenter__(self) -> QuickBooksClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _update_access_token(self, token_info: Any) -> None:  # noqa: ANN401
        """Update the access token in headers.

        Args:
            token_info: QuickBooksTokenInfo instance
        """
        self.headers["Authorization"] = f"Bearer {token_info.access_token}"
        self._client.headers["Authorization"] = f"Bearer {token_info.access_token}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to QuickBooks API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON body data
            params: Query parameters
            retry_on_401: Whether to retry with refreshed token on 401

        Returns:
            Response data

        Raises:
            QuickBooksError: If request fails
        """
        # Ensure we have a valid token before making request
        if self.oauth_manager:
            try:
                access_token = await self.oauth_manager.get_valid_access_token()
                self.headers["Authorization"] = f"Bearer {access_token}"
                self._client.headers["Authorization"] = f"Bearer {access_token}"
            except Exception as e:
                logger.error("Failed to get valid access token: %s", e)
                raise QuickBooksError(f"OAuth error: {e}") from e

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
            # Handle 401 Unauthorized - token might have just expired
            if e.response.status_code == 401 and retry_on_401 and self.oauth_manager:
                logger.info("Got 401, attempting token refresh and retry")
                try:
                    # Force token refresh
                    await self.oauth_manager.refresh_access_token()
                    # Retry the request once
                    return await self._request(
                        method,
                        endpoint,
                        json=json,
                        params=params,
                        retry_on_401=False,  # Don't retry again
                    )
                except Exception:
                    logger.exception("Token refresh failed on 401 retry")
                    # Fall through to original error

            logger.error("QuickBooks API error: %s", e.response.text)
            raise QuickBooksError(f"API request failed: {e}") from e
        except httpx.RequestError as e:
            logger.error("Request error: %s", e)
            raise QuickBooksError(f"Request failed: {e}") from e

    async def get(
        self, endpoint: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, json=json, params=params)

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

    async def get_bank_accounts(self) -> list[AccountInfo]:
        """Get all bank accounts for payment methods."""
        query = "SELECT * FROM Account WHERE AccountType = 'Bank' AND Active = true"
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

    async def get_credit_card_accounts(self) -> list[AccountInfo]:
        """Get all credit card accounts for payment methods."""
        query = (
            "SELECT * FROM Account WHERE AccountType = 'Credit Card' "
            "AND Active = true"
        )
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

        # Get payment accounts (bank or credit card)
        payment_account = await self._get_payment_account()

        # Build purchase data
        purchase_data = self._build_purchase_data(
            expense=expense,
            vendor_id=vendor_id,
            vendor_name=expense.vendor_name,
            expense_account=account,
            payment_account=payment_account,
        )

        return await self.client.post("purchase", json=purchase_data)

    async def _get_payment_account(self) -> AccountInfo:
        """Get a payment account (prefer bank, fallback to credit card)."""
        # Try bank accounts first
        bank_accounts = await self.get_bank_accounts()
        if bank_accounts:
            return bank_accounts[0]  # Use first bank account

        # Fallback to credit card accounts
        credit_accounts = await self.get_credit_card_accounts()
        if credit_accounts:
            return credit_accounts[0]  # Use first credit card account

        raise QuickBooksError("No payment accounts (Bank or Credit Card) found")

    def _build_purchase_data(
        self,
        *,
        expense: Expense,
        vendor_id: str,
        vendor_name: str,
        expense_account: AccountInfo,
        payment_account: AccountInfo,
    ) -> dict[str, Any]:
        """Build purchase data for QuickBooks API."""
        base_amount = expense.amount - expense.tax_amount
        line_items = [
            {
                "Amount": float(base_amount),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {
                        "value": expense_account.id,
                        "name": expense_account.name,
                    }
                },
                "Description": expense.category,
            }
        ]

        # Add tax line if applicable
        if expense.tax_amount > Decimal(0):
            line_items.append(
                {
                    "Amount": float(expense.tax_amount),
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": expense_account.id, "name": "Sales Tax"}
                    },
                    "Description": "Tax",
                }
            )

        return {
            "PaymentType": "Cash",
            "AccountRef": {"value": payment_account.id, "name": payment_account.name},
            "EntityRef": {"value": vendor_id, "name": vendor_name},
            "TotalAmt": float(expense.amount),
            "TxnDate": expense.date.isoformat(),
            "CurrencyRef": {"value": expense.currency},
            "Line": line_items,
        }
