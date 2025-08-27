from fastapi import FastAPI, HTTPException

from models import ReceiptData
from quickbooks_client import QuickBooksClient

app = FastAPI(title="Receipt Scanner", version="1.0.0")
qb_client = QuickBooksClient()


@app.get("/")
def root():
    return {
        "message": "Receipt Scanner API - Ready for QuickBooks testing!",
        "help": "Visit /help for curl commands",
    }


@app.get("/help")
def help_commands():
    """Display all curl commands for terminal usage"""
    return {
        "title": "QuickBooks Receipt Scanner - Terminal Commands",
        "description": "Copy and paste these curl commands to interact with the API",
        "commands": {
            "1. Test Connection": {
                "description": "Verify QuickBooks API connection",
                "command": "curl http://localhost:8000/test-connection",
            },
            "2. Search Vendor": {
                "description": "Search for a vendor by name",
                "command": "curl http://localhost:8000/vendors/Starbucks",
            },
            "3. Create Vendor": {
                "description": "Create a new vendor",
                "command": "curl -X POST http://localhost:8000/vendors?vendor_name=Coffee%20Shop",
            },
            "4. Get Expense Accounts": {
                "description": "List all expense accounts",
                "command": "curl http://localhost:8000/accounts/expense",
            },
            "5. Create Expense from Receipt": {
                "description": "Convert receipt data to QuickBooks expense",
                "command": """curl -X POST http://localhost:8000/expenses \\
  -H "Content-Type: application/json" \\
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "2024-01-15",
    "currency": "USD",
    "category": "Office Supplies",
    "tax_amount": 3.42
  }'""",
            },
        },
        "examples": {
            "Simple Receipt": {
                "description": "Basic expense without tax",
                "command": """curl -X POST http://localhost:8000/expenses \\
  -H "Content-Type: application/json" \\
  -d '{
    "vendor_name": "Starbucks",
    "amount": 12.50,
    "date": "2024-01-15",
    "currency": "USD",
    "category": "Meals"
  }'""",
            },
            "Receipt with Tax": {
                "description": "Expense with separate tax amount",
                "command": """curl -X POST http://localhost:8000/expenses \\
  -H "Content-Type: application/json" \\
  -d '{
    "vendor_name": "Best Buy",
    "amount": 129.99,
    "date": "2024-01-15",
    "currency": "USD",
    "category": "Equipment",
    "tax_amount": 10.40
  }'""",
            },
        },
        "workflow": [
            "1. Test connection to ensure QuickBooks is accessible",
            "2. Create expense using receipt data",
            "3. API will automatically handle vendor creation if needed",
            "4. Expense will be created in QuickBooks with proper categorization",
        ],
        "notes": [
            "Replace localhost:8000 with your actual server URL",
            "Ensure your .env file contains valid QuickBooks tokens",
            "Access tokens expire every hour - re-run oauth_setup.py if needed",
            "All amounts should be in decimal format (e.g., 12.50)",
        ],
    }


@app.get("/test-connection")
def test_quickbooks_connection():
    """Test QuickBooks API connection"""
    try:
        result = qb_client.test_connection()
        return {"status": "connected", "company": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {e!s}")


@app.get("/vendors/{vendor_name}")
def search_vendor(vendor_name: str):
    """Search for a vendor by name"""
    try:
        result = qb_client.search_vendor(vendor_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vendors")
def create_vendor(vendor_name: str):
    """Create a new vendor"""
    try:
        result = qb_client.create_vendor(vendor_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accounts/expense")
def get_expense_accounts():
    """Get all expense accounts"""
    try:
        result = qb_client.get_expense_accounts()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/expenses")
def create_expense(receipt: ReceiptData):
    """Create expense from receipt data"""
    try:
        # 1. Check if vendor exists
        vendor_result = qb_client.search_vendor(receipt.vendor_name)
        vendors = vendor_result.get("QueryResponse", {}).get("Vendor", [])

        if not vendors:
            # Create vendor
            create_result = qb_client.create_vendor(receipt.vendor_name)
            vendor_id = create_result["QueryResponse"]["Vendor"][0]["Id"]
        else:
            vendor_id = vendors[0]["Id"]

        # 2. Get expense account (use first available)
        accounts_result = qb_client.get_expense_accounts()
        accounts = accounts_result.get("QueryResponse", {}).get("Account", [])
        if not accounts:
            raise HTTPException(status_code=400, detail="No expense accounts found")
        account_id = accounts[0]["Id"]

        # 3. Create expense
        expense_result = qb_client.create_expense(
            vendor_id=vendor_id,
            vendor_name=receipt.vendor_name,
            amount=receipt.amount,
            date=receipt.date,
            account_id=account_id,
            account_name=accounts[0].get("Name", "Office Supplies"),
            tax_amount=getattr(receipt, "tax_amount", 0.0),
        )

        return {
            "status": "success",
            "vendor_id": vendor_id,
            "expense": expense_result,
            "message": f"Expense created for {receipt.vendor_name} - ${receipt.amount}",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
