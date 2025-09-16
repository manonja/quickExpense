#\!/usr/bin/env python3
"""Search for expenses by vendor name."""

import asyncio
import sys
from pathlib import Path

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


async def search_vendor_expenses(vendor_name: str):
    """Search for expenses by vendor."""
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
            # First, get the vendor ID
            vendor_query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}'"
            vendor_response = await client.get("query", params={"query": vendor_query})
            vendors = vendor_response.get("QueryResponse", {}).get("Vendor", [])
            
            if not vendors:
                print(f"❌ Vendor '{vendor_name}' not found")
                return
            
            vendor_id = vendors[0]["Id"]
            print(f"✅ Found vendor '{vendor_name}' (ID: {vendor_id})")
            
            # Get all purchases and filter by vendor (EntityRef isn't queryable)
            purchase_query = "SELECT * FROM Purchase"
            response = await client.get("query", params={"query": purchase_query})
            all_purchases = response.get("QueryResponse", {}).get("Purchase", [])
            
            # Filter by vendor ID
            purchases = [
                p for p in all_purchases 
                if p.get("EntityRef", {}).get("value") == vendor_id
            ]
            
            print(f"\n📊 Expenses for {vendor_name}")
            print("=" * 60)
            
            if not purchases:
                print("No expenses found for this vendor.")
                return
            
            total = 0
            for purchase in purchases:
                print(f"\nID: {purchase.get('Id')}")
                print(f"Date: {purchase.get('TxnDate')}")
                print(f"Amount: ${purchase.get('TotalAmt')}")
                print(f"Currency: {purchase.get('CurrencyRef', {}).get('value', 'USD')}")
                print(f"Type: {purchase.get('PaymentType')}")
                print(f"Account: {purchase.get('AccountRef', {}).get('name', 'Unknown')}")
                
                total += float(purchase.get('TotalAmt', 0))
            
            print(f"\n{'=' * 60}")
            print(f"Total: ${total:.2f}")
            print(f"Count: {len(purchases)} expenses")
            
        except Exception as e:
            print(f"❌ Error searching expenses: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python search_vendor_expenses.py <vendor_name>")
        print("Example: python search_vendor_expenses.py Harrods")
        sys.exit(1)
    
    vendor_name = sys.argv[1]
    print(f"🔍 Searching expenses for vendor: {vendor_name}")
    
    asyncio.run(search_vendor_expenses(vendor_name))


if __name__ == "__main__":
    main()
