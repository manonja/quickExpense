from fastapi import FastAPI, HTTPException
from models import ReceiptData
from quickbooks_client import QuickBooksClient

app = FastAPI(title="Receipt Scanner", version="1.0.0")
qb_client = QuickBooksClient()

@app.get("/")
def root():
    return {"message": "Receipt Scanner API - Ready for QuickBooks testing!"}

@app.get("/test-connection")
def test_quickbooks_connection():
    """Test QuickBooks API connection"""
    try:
        result = qb_client.test_connection()
        return {"status": "connected", "company": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

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
        vendors = vendor_result.get('QueryResponse', {}).get('Vendor', [])
        
        if not vendors:
            # Create vendor
            create_result = qb_client.create_vendor(receipt.vendor_name)
            vendor_id = create_result['QueryResponse']['Vendor'][0]['Id']
        else:
            vendor_id = vendors[0]['Id']
        
        # 2. Get expense account (use first available)
        accounts_result = qb_client.get_expense_accounts()
        accounts = accounts_result.get('QueryResponse', {}).get('Account', [])
        if not accounts:
            raise HTTPException(status_code=400, detail="No expense accounts found")
        account_id = accounts[0]['Id']
        
        # 3. Create bill
        bill_result = qb_client.create_bill(
            vendor_id=vendor_id,
            amount=receipt.amount,
            date=receipt.date,
            account_id=account_id
        )
        
        return {
            "status": "success",
            "vendor_id": vendor_id,
            "bill": bill_result,
            "message": f"Expense created for {receipt.vendor_name} - ${receipt.amount}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
