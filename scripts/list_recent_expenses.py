#!/usr/bin/env python3
"""List recent expenses from QuickBooks."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quickexpense.core.config import get_settings
from src.quickexpense.services.quickbooks import QuickBooksClient
from src.quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from src.quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenResponse,
)
from src.quickexpense.services.token_store import TokenStore


async def list_recent_expenses(days: int = 30):
    """List recent expenses from QuickBooks."""
    settings = get_settings()
    token_store = TokenStore()
    token_data = token_store.load_tokens()
    
    if not token_data:
        print("❌ No authentication tokens found. Run: quickexpense auth")
        return
    
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
        x_refresh_token_expires_in=token_data.get("x_refresh_token_expires_in", 8640000),
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
            # Query recent purchases
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            query = f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' ORDERBY TxnDate DESC"
            
            response = await client.get("query", params={"query": query})
            purchases = response.get("QueryResponse", {}).get("Purchase", [])
            
            print(f"\n📊 Recent Expenses (last {days} days)")
            print("=" * 60)
            
            if not purchases:
                print("No expenses found.")
                return
            
            total = 0
            for purchase in purchases:
                print(f"\nID: {purchase.get('Id')}")
                print(f"Date: {purchase.get('TxnDate')}")
                print(f"Vendor: {purchase.get('EntityRef', {}).get('name', 'Unknown')}")
                print(f"Amount: ${purchase.get('TotalAmt')}")
                print(f"Type: {purchase.get('PaymentType')}")
                
                total += float(purchase.get('TotalAmt', 0))
            
            print(f"\n{'=' * 60}")
            print(f"Total: ${total:.2f}")
            print(f"Count: {len(purchases)} expenses")
            
        except Exception as e:
            print(f"❌ Error listing expenses: {e}")


def main():
    """Main entry point."""
    days = 365  # Look back 1 year to find our test expense
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    
    print(f"🔍 Listing expenses from the last {days} days...")
    
    asyncio.run(list_recent_expenses(days))


if __name__ == "__main__":
    main()