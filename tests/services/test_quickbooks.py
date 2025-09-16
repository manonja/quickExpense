"""Tests for QuickBooks service with OAuth integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from quickexpense.models import Expense
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
)
from quickexpense.services.quickbooks import (
    AccountInfo,
    QuickBooksClient,
    QuickBooksError,
    QuickBooksService,
    VendorSearchResult,
)
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager


@pytest.fixture
def valid_token_info() -> QuickBooksTokenInfo:
    """Create valid token info for testing."""
    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=100),
    )


@pytest.fixture
def oauth_config() -> QuickBooksOAuthConfig:
    """Create test OAuth configuration."""
    return QuickBooksOAuthConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
    )


@pytest.fixture
def mock_oauth_manager(
    oauth_config: QuickBooksOAuthConfig,
    valid_token_info: QuickBooksTokenInfo,
) -> MagicMock:
    """Create mock OAuth manager."""
    manager = MagicMock(spec=QuickBooksOAuthManager)
    manager.config = oauth_config
    manager.tokens = valid_token_info
    manager.get_valid_access_token = AsyncMock(
        return_value=valid_token_info.access_token
    )
    manager.refresh_access_token = AsyncMock(return_value=valid_token_info)
    manager.add_token_update_callback = MagicMock()
    return manager


@pytest.fixture
def sample_expense() -> Expense:
    """Create sample expense for testing."""
    return Expense(
        vendor_name="Test Vendor",
        amount=Decimal("100.50"),
        date=datetime.now(UTC).date(),
        category="Office Supplies",
        tax_amount=Decimal("8.50"),
        currency="USD",
    )


class TestQuickBooksClient:
    """Tests for QuickBooksClient with OAuth integration."""

    @pytest.mark.asyncio
    async def test_init_with_oauth_manager(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test client initialization with OAuth manager."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )

        assert client.oauth_manager == mock_oauth_manager
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Bearer valid_access_token"
        mock_oauth_manager.add_token_update_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_without_oauth_manager(self) -> None:
        """Test client initialization without OAuth manager."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            access_token="static_token",
        )

        assert client.oauth_manager is None
        assert client.headers["Authorization"] == "Bearer static_token"

    @pytest.mark.asyncio
    async def test_init_no_token_error(self) -> None:
        """Test client initialization error when no token provided."""
        with pytest.raises(
            ValueError,
            match="Either access_token or oauth_manager with tokens required",
        ):
            QuickBooksClient(
                base_url="https://sandbox-quickbooks.api.intuit.com",
                company_id="test_company",
            )

    @pytest.mark.asyncio
    async def test_token_update_callback(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test token update callback functionality."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )

        # Get the callback function
        callback = mock_oauth_manager.add_token_update_callback.call_args[0][0]

        # Create new token info
        new_token_info = MagicMock()
        new_token_info.access_token = "new_access_token"

        # Call the callback
        callback(new_token_info)

        # Verify headers updated
        assert client.headers["Authorization"] == "Bearer new_access_token"
        assert client._client.headers["Authorization"] == "Bearer new_access_token"

    @pytest.mark.asyncio
    async def test_request_with_token_refresh(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test request that triggers token refresh."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )

        # Mock the actual HTTP client
        with patch.object(client._client, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response

            # Make request
            result = await client._request("GET", "test/endpoint")

            # Verify token was refreshed
            mock_oauth_manager.get_valid_access_token.assert_called_once()
            assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_request_401_with_retry(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test request that gets 401 and retries with refreshed token."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )

        # Mock the HTTP client to return 401 first, then success
        with patch.object(client._client, "request") as mock_request:
            # First call: 401 error
            mock_401_response = MagicMock()
            mock_401_response.status_code = 401
            mock_401_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_401_response,
            )

            # Second call: success
            mock_success_response = MagicMock()
            mock_success_response.json.return_value = {"data": "success"}

            mock_request.side_effect = [mock_401_response, mock_success_response]

            # Make request
            result = await client._request("GET", "test/endpoint")

            # Verify token was refreshed after 401
            mock_oauth_manager.refresh_access_token.assert_called_once()
            assert result == {"data": "success"}
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_request_401_no_oauth_manager(self) -> None:
        """Test 401 error without OAuth manager."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            access_token="static_token",
        )

        with patch.object(client._client, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            with pytest.raises(QuickBooksError, match="API request failed"):
                await client._request("GET", "test/endpoint")

    @pytest.mark.asyncio
    async def test_request_network_error(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test request with network error."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )

        with patch.object(client._client, "request") as mock_request:
            mock_request.side_effect = httpx.RequestError("Network error")

            with pytest.raises(QuickBooksError, match="Request failed"):
                await client._request("GET", "test/endpoint")

    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test client as async context manager."""
        async with QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        ) as client:
            assert client is not None

        # Client should be closed after exiting


class TestQuickBooksService:
    """Tests for QuickBooksService."""

    @pytest.mark.asyncio
    async def test_test_connection(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test connection testing."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"CompanyName": "Test Company"}

            result = await service.test_connection()
            assert result == {"CompanyName": "Test Company"}
            mock_get.assert_called_once_with("companyinfo/test_company")

    @pytest.mark.asyncio
    async def test_search_vendor(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test vendor search."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {
                "QueryResponse": {
                    "Vendor": [
                        {
                            "Id": "1",
                            "DisplayName": "Test Vendor",
                            "Active": True,
                        },
                        {
                            "Id": "2",
                            "DisplayName": "Test Vendor 2",
                            "Active": False,
                        },
                    ]
                }
            }

            results = await service.search_vendor("Test Vendor")
            assert len(results) == 2
            assert isinstance(results[0], VendorSearchResult)
            assert results[0].id == "1"
            assert results[0].display_name == "Test Vendor"
            assert results[0].active is True

    @pytest.mark.asyncio
    async def test_create_vendor(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test vendor creation."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with patch.object(client, "post") as mock_post:
            mock_post.return_value = {
                "Vendor": {
                    "Id": "3",
                    "DisplayName": "New Vendor",
                    "Active": True,
                }
            }

            result = await service.create_vendor("New Vendor")
            assert isinstance(result, VendorSearchResult)
            assert result.id == "3"
            assert result.display_name == "New Vendor"
            mock_post.assert_called_once_with(
                "vendor",
                json={"DisplayName": "New Vendor", "Active": True},
            )

    @pytest.mark.asyncio
    async def test_get_expense_accounts(
        self,
        mock_oauth_manager: MagicMock,
    ) -> None:
        """Test getting expense accounts."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {
                "QueryResponse": {
                    "Account": [
                        {
                            "Id": "1",
                            "Name": "Office Supplies",
                            "AccountType": "Expense",
                            "Active": True,
                        },
                        {
                            "Id": "2",
                            "Name": "Travel",
                            "AccountType": "Expense",
                        },
                    ]
                }
            }

            results = await service.get_expense_accounts()
            assert len(results) == 2
            assert isinstance(results[0], AccountInfo)
            assert results[0].id == "1"
            assert results[0].name == "Office Supplies"
            assert results[0].active is True

    @pytest.mark.asyncio
    async def test_create_expense_new_vendor(
        self,
        mock_oauth_manager: MagicMock,
        sample_expense: Expense,
    ) -> None:
        """Test expense creation with new vendor."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with (
            patch.object(service, "search_vendor") as mock_search,
            patch.object(service, "create_vendor") as mock_create_vendor,
            patch.object(service, "get_expense_accounts") as mock_get_accounts,
            patch.object(client, "post") as mock_post,
        ):
            # No existing vendor
            mock_search.return_value = []

            # Create vendor returns new vendor
            mock_create_vendor.return_value = VendorSearchResult(
                id="new_vendor_id",
                display_name="Test Vendor",
                active=True,
            )

            # Mock accounts
            mock_get_accounts.return_value = [
                AccountInfo(
                    id="account_1",
                    name="Office Supplies",
                    account_type="Expense",
                    active=True,
                )
            ]

            # Mock purchase creation
            mock_post.return_value = {"Purchase": {"Id": "purchase_1"}}

            result = await service.create_expense(sample_expense)

            # Verify vendor was created
            mock_create_vendor.assert_called_once_with("Test Vendor")
            assert result == {"Purchase": {"Id": "purchase_1"}}

    @pytest.mark.asyncio
    async def test_create_expense_existing_vendor(
        self,
        mock_oauth_manager: MagicMock,
        sample_expense: Expense,
    ) -> None:
        """Test expense creation with existing vendor."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with (
            patch.object(service, "search_vendor") as mock_search,
            patch.object(service, "get_expense_accounts") as mock_get_accounts,
            patch.object(client, "post") as mock_post,
        ):
            # Existing vendor found
            mock_search.return_value = [
                VendorSearchResult(
                    id="existing_vendor_id",
                    display_name="Test Vendor",
                    active=True,
                )
            ]

            # Mock accounts
            mock_get_accounts.return_value = [
                AccountInfo(
                    id="account_1",
                    name="Office Supplies",
                    account_type="Expense",
                    active=True,
                )
            ]

            # Mock purchase creation
            mock_post.return_value = {"Purchase": {"Id": "purchase_2"}}

            result = await service.create_expense(sample_expense)

            # Verify existing vendor was used
            assert result == {"Purchase": {"Id": "purchase_2"}}
            mock_post.assert_called_once()
            call_data = mock_post.call_args[1]["json"]
            assert call_data["EntityRef"]["value"] == "existing_vendor_id"

    @pytest.mark.asyncio
    async def test_create_expense_no_accounts(
        self,
        mock_oauth_manager: MagicMock,
        sample_expense: Expense,
    ) -> None:
        """Test expense creation when no expense accounts found."""
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id="test_company",
            oauth_manager=mock_oauth_manager,
        )
        service = QuickBooksService(client)

        with (
            patch.object(service, "search_vendor") as mock_search,
            patch.object(service, "create_vendor") as mock_create_vendor,
            patch.object(service, "get_expense_accounts") as mock_get_accounts,
        ):
            # No existing vendor
            mock_search.return_value = []
            # Create vendor returns new vendor
            mock_create_vendor.return_value = VendorSearchResult(
                id="new_vendor_id",
                display_name="Test Vendor",
                active=True,
            )
            # No expense accounts
            mock_get_accounts.return_value = []

            with pytest.raises(QuickBooksError, match="No expense accounts found"):
                await service.create_expense(sample_expense)

    def test_build_purchase_data(
        self,
        sample_expense: Expense,
    ) -> None:
        """Test building purchase data for API."""
        client = MagicMock()
        service = QuickBooksService(client)

        from quickexpense.services.quickbooks import AccountInfo

        expense_account = AccountInfo(
            id="account_1",
            name="Office Supplies",
            account_type="Expense",
            active=True,
        )
        payment_account = AccountInfo(
            id="payment_1",
            name="Chequing",
            account_type="Bank",
            active=True,
        )

        data = service._build_purchase_data(
            expense=sample_expense,
            vendor_id="vendor_1",
            vendor_name="Test Vendor",
            expense_account=expense_account,
            payment_account=payment_account,
        )

        assert data["PaymentType"] == "Cash"
        assert data["AccountRef"]["value"] == "payment_1"
        assert data["EntityRef"]["value"] == "vendor_1"
        assert data["TotalAmt"] == 100.5
        assert data["TxnDate"] == sample_expense.date.isoformat()
        assert data["CurrencyRef"]["value"] == "USD"

        # Check line items
        assert len(data["Line"]) == 2  # Base amount + tax
        assert data["Line"][0]["Amount"] == 92.0  # 100.50 - 8.50
        assert data["Line"][1]["Amount"] == 8.5  # Tax
