#!/usr/bin/env python3
"""Direct QuickBooks API test to verify authentication."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_quickbooks_connection():
    """Test QuickBooks API connection directly."""

    company_id = os.getenv("QB_COMPANY_ID")
    access_token = os.getenv("QB_ACCESS_TOKEN")
    base_url = os.getenv("QB_BASE_URL", "https://sandbox-quickbooks.api.intuit.com")

    if not company_id or not access_token:
        print("❌ Missing QB_COMPANY_ID or QB_ACCESS_TOKEN in .env")
        return False

    url = f"{base_url}/v3/company/{company_id}/companyinfo/{company_id}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    print("🔍 Testing QuickBooks connection...")
    print(f"   Company ID: {company_id}")
    print(f"   URL: {url}")
    print(f"   Token: {access_token[:20]}...{access_token[-10:]}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                company_name = data.get("CompanyInfo", {}).get("CompanyName", "Unknown")
                print(f"\n✅ SUCCESS! Connected to: {company_name}")
                return True
            if response.status_code == 401:
                print("\n❌ Authentication failed - Token expired or invalid")
                print(f"   Response: {response.text[:200]}")
                print("\n💡 Run this to get new tokens:")
                print("   uv run python scripts/connect_quickbooks_cli.py")
                return False
            print(f"\n❌ Unexpected error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

        except Exception as e:
            print(f"\n❌ Connection error: {e}")
            return False


if __name__ == "__main__":
    success = asyncio.run(test_quickbooks_connection())
    exit(0 if success else 1)
