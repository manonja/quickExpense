#!/usr/bin/env python3
"""Integration test script for QuickExpense application.

This script tests the complete flow of the application including:
1. Health checks
2. QuickBooks connection
3. Expense creation
4. Receipt extraction
5. OAuth token handling
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_step(message: str) -> None:
    """Print a test step."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}▶ {message}{Colors.RESET}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")


def print_json(data: dict[str, Any]) -> None:
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2, default=str))


async def test_health_endpoints(client: httpx.AsyncClient) -> bool:
    """Test health check endpoints."""
    print_step("Testing health check endpoints")

    try:
        # Test /health endpoint
        response = await client.get("/health")
        if response.status_code == 200:
            print_success("GET /health - OK")
            print_json(response.json())
        else:
            print_error(f"GET /health - Failed with status {response.status_code}")
            return False

        # Test /ready endpoint
        response = await client.get("/ready")
        if response.status_code == 200:
            print_success("GET /ready - OK")
            print_json(response.json())
        else:
            print_error(f"GET /ready - Failed with status {response.status_code}")
            return False

        return True

    except Exception as e:
        print_error(f"Health check error: {e}")
        return False


async def test_api_info(client: httpx.AsyncClient) -> bool:
    """Test API info endpoint."""
    print_step("Testing API info endpoint")

    try:
        response = await client.get(f"{API_PREFIX}/")
        if response.status_code == 200:
            print_success(f"GET {API_PREFIX}/ - OK")
            print_json(response.json())
            return True
        print_error(f"GET {API_PREFIX}/ - Failed with status {response.status_code}")
        return False

    except Exception as e:
        print_error(f"API info error: {e}")
        return False


async def test_quickbooks_connection(client: httpx.AsyncClient) -> bool:
    """Test QuickBooks connection."""
    print_step("Testing QuickBooks connection")

    try:
        response = await client.get(f"{API_PREFIX}/test-connection")
        if response.status_code == 200:
            print_success(f"GET {API_PREFIX}/test-connection - OK")
            data = response.json()
            print_info(
                f"Connected to: {data.get('CompanyInfo', {}).get('CompanyName', 'Unknown')}"
            )
            return True
        if response.status_code == 401:
            print_error("QuickBooks authentication failed - tokens may be expired")
            print_info("Run: uv run python scripts/connect_quickbooks_cli.py")
            return False
        print_error(f"Connection test failed with status {response.status_code}")
        return False

    except Exception as e:
        print_error(f"QuickBooks connection error: {e}")
        return False


async def test_vendor_operations(client: httpx.AsyncClient) -> tuple[bool, str | None]:
    """Test vendor search and creation."""
    print_step("Testing vendor operations")

    test_vendor_name = f"Test Vendor {datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # Search for vendor (should not exist)
        print_info(f"Searching for vendor: {test_vendor_name}")
        response = await client.get(f"{API_PREFIX}/vendors/{test_vendor_name}")

        if response.status_code == 200:
            vendors = response.json()
            if len(vendors) == 0:
                print_success("Vendor search returned empty (as expected)")
            else:
                print_info(f"Found {len(vendors)} existing vendors")

        # Create vendor
        print_info(f"Creating vendor: {test_vendor_name}")
        response = await client.post(
            f"{API_PREFIX}/vendors", params={"vendor_name": test_vendor_name}
        )

        if response.status_code == 200:
            vendor = response.json()
            print_success(f"Created vendor with ID: {vendor['id']}")
            return True, test_vendor_name
        print_error(f"Vendor creation failed with status {response.status_code}")
        return False, None

    except Exception as e:
        print_error(f"Vendor operations error: {e}")
        return False, None


async def test_expense_creation(
    client: httpx.AsyncClient, vendor_name: str | None = None
) -> bool:
    """Test expense creation."""
    print_step("Testing expense creation")

    if not vendor_name:
        vendor_name = "Office Depot"

    expense_data = {
        "vendor_name": vendor_name,
        "amount": "45.99",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "currency": "USD",
        "category": "Office Supplies",
        "tax_amount": "3.42",
        "description": "Integration test expense",
    }

    try:
        print_info("Creating expense:")
        print_json(expense_data)

        response = await client.post(f"{API_PREFIX}/expenses", json=expense_data)

        if response.status_code == 200:
            result = response.json()
            print_success("Created expense successfully")
            print_info(
                f"QuickBooks Purchase ID: {result.get('data', {}).get('Purchase', {}).get('Id', 'Unknown')}"
            )
            return True
        print_error(f"Expense creation failed with status {response.status_code}")
        print_json(response.json())
        return False

    except Exception as e:
        print_error(f"Expense creation error: {e}")
        return False


async def test_receipt_extraction(client: httpx.AsyncClient) -> bool:
    """Test Gemini receipt extraction."""
    print_step("Testing receipt extraction")

    # Check if Gemini API key is configured
    if (
        not os.getenv("GEMINI_API_KEY")
        or os.getenv("GEMINI_API_KEY") == "your_gemini_api_key_here"
    ):
        print_info("Gemini API key not configured - skipping receipt extraction test")
        return True

    # Create a simple test image (1x1 white pixel PNG)
    test_image_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
        "60e6kgAAAABJRU5ErkJggg=="
    )

    receipt_data = {
        "image_base64": test_image_base64,
        "category": "Office Supplies",
        "additional_context": "Integration test receipt",
    }

    try:
        print_info("Extracting receipt data from test image")

        response = await client.post(
            f"{API_PREFIX}/receipts/extract", json=receipt_data
        )

        if response.status_code == 200:
            result = response.json()
            print_success("Receipt extraction successful")
            print_info("Extracted data:")
            print_json(result.get("receipt", {}))
            return True
        print_error(f"Receipt extraction failed with status {response.status_code}")
        print_json(response.json())
        return False

    except Exception as e:
        print_error(f"Receipt extraction error: {e}")
        return False


async def test_expense_accounts(client: httpx.AsyncClient) -> bool:
    """Test listing expense accounts."""
    print_step("Testing expense accounts listing")

    try:
        response = await client.get(f"{API_PREFIX}/accounts/expense")

        if response.status_code == 200:
            accounts = response.json()
            print_success(f"Found {len(accounts)} expense accounts")
            if accounts:
                print_info("First 5 accounts:")
                for account in accounts[:5]:
                    print(f"  - {account['name']} (ID: {account['id']})")
            return True
        print_error(f"Account listing failed with status {response.status_code}")
        return False

    except Exception as e:
        print_error(f"Account listing error: {e}")
        return False


async def run_integration_tests() -> None:
    """Run all integration tests."""
    print(f"\n{Colors.BOLD}QuickExpense Integration Tests{Colors.RESET}")
    print("=" * 50)

    # Check if server is running
    print_step("Checking if server is running")
    try:
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            await client.get("/health")
            print_success(f"Server is running at {BASE_URL}")
    except httpx.ConnectError:
        print_error(f"Server is not running at {BASE_URL}")
        print_info("Start the server with: uv run fastapi dev src/quickexpense/main.py")
        return

    # Run tests
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        tests_passed = 0
        total_tests = 0

        # Health checks
        total_tests += 1
        if await test_health_endpoints(client):
            tests_passed += 1

        # API info
        total_tests += 1
        if await test_api_info(client):
            tests_passed += 1

        # QuickBooks connection
        total_tests += 1
        qb_connected = await test_quickbooks_connection(client)
        if qb_connected:
            tests_passed += 1

            # Only run QuickBooks-dependent tests if connected
            # Expense accounts
            total_tests += 1
            if await test_expense_accounts(client):
                tests_passed += 1

            # Vendor operations
            total_tests += 1
            vendor_success, vendor_name = await test_vendor_operations(client)
            if vendor_success:
                tests_passed += 1

                # Expense creation with new vendor
                total_tests += 1
                if await test_expense_creation(client, vendor_name):
                    tests_passed += 1

        # Receipt extraction (can run even without QB connection)
        total_tests += 1
        if await test_receipt_extraction(client):
            tests_passed += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}Test Summary{Colors.RESET}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {Colors.GREEN}{tests_passed}{Colors.RESET}")
    print(f"Failed: {Colors.RED}{total_tests - tests_passed}{Colors.RESET}")

    if tests_passed == total_tests:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! 🎉{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed.{Colors.RESET}")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
