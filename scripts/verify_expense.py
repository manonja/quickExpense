#!/usr/bin/env python3
"""Verify an expense was created in QuickBooks by Purchase ID."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quickexpense.core.config import get_settings
from src.quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenResponse,
)
from src.quickexpense.services.quickbooks import QuickBooksClient
from src.quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from src.quickexpense.services.token_store import TokenStore


async def verify_expense(purchase_id: str):
    """Verify an expense exists in QuickBooks."""
    settings = get_settings()
    token_store = TokenStore()
    token_data = token_store.load_tokens()

    if not token_data:
        print("❌ No authentication tokens found. Run: quickexpense auth")
        return None

    # Set up OAuth manager
    oauth_config = QuickBooksOAuthConfig(
        client_id=settings.qb_client_id,
        client_secret=settings.qb_client_secret,
        redirect_uri=settings.qb_redirect_uri,
    )

    token_response = QuickBooksTokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 3600),
        x_refresh_token_expires_in=token_data.get(
            "x_refresh_token_expires_in", 8640000
        ),
        token_type=token_data.get("token_type", "bearer"),
    )

    oauth_manager = QuickBooksOAuthManager(
        oauth_config, initial_tokens=token_response.to_token_info()
    )

    # Create client
    async with QuickBooksClient(
        base_url=str(settings.qb_base_url),
        company_id=token_data["company_id"],
        oauth_manager=oauth_manager,
    ) as client:
        try:
            # Get the purchase
            response = await client.get(f"purchase/{purchase_id}")
            purchase = response.get("Purchase", {})

            print(f"\n✅ Found Purchase ID: {purchase.get('Id')}")
            print(f"   Date: {purchase.get('TxnDate')}")
            print(f"   Vendor: {purchase.get('EntityRef', {}).get('name')}")
            print(f"   Total: ${purchase.get('TotalAmt')}")
            print(f"   Payment Type: {purchase.get('PaymentType')}")
            print(f"   Payment Account: {purchase.get('AccountRef', {}).get('name')}")

            # Show line items
            if purchase.get("Line"):
                print("\n   Line Items:")
                for line in purchase["Line"]:
                    if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                        account = line["AccountBasedExpenseLineDetail"]["AccountRef"][
                            "name"
                        ]
                        print(f"   - ${line.get('Amount')} → {account}")

            return purchase

        except Exception as e:
            print(f"❌ Error fetching purchase: {e}")
            return None


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python verify_expense.py <purchase_id>")
        print("Example: python verify_expense.py 185")
        sys.exit(1)

    purchase_id = sys.argv[1]
    print(f"🔍 Verifying Purchase ID: {purchase_id}")

    asyncio.run(verify_expense(purchase_id))


if __name__ == "__main__":
    main()
