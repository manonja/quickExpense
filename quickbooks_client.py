import httpx
from config import settings

class QuickBooksClient:
    def __init__(self):
        self.base_url = settings.qb_base_url
        self.company_id = settings.qb_company_id
        self.headers = {
            "Authorization": f"Bearer {settings.qb_access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data=None):
        url = f"{self.base_url}/v3/company/{self.company_id}/{endpoint}"
        
        with httpx.Client() as client:
            if method == "GET":
                response = client.get(url, headers=self.headers)
            elif method == "POST":
                response = client.post(url, headers=self.headers, json=data)
            
            return response.json()
    
    def test_connection(self):
        return self._make_request("GET", f"companyinfo/{self.company_id}")
    
    def search_vendor(self, vendor_name: str):
        query = f"SELECT * FROM Vendor WHERE Name = '{vendor_name}'"
        return self._make_request("GET", f"query?query={query}")
    
    def create_vendor(self, vendor_name: str):
        data = {
            "Vendor": {
                "Name": vendor_name,
                "CompanyName": vendor_name
            }
        }
        return self._make_request("POST", "vendor", data)
    
    def get_expense_accounts(self):
        query = "SELECT * FROM Account WHERE AccountType = 'Expense'"
        return self._make_request("GET", f"query?query={query}")
    
    def create_bill(self, vendor_id: str, amount: float, date: str, account_id: str):
        data = {
            "Bill": {
                "VendorRef": {"value": vendor_id},
                "TxnDate": date,
                "DueDate": date,
                "TotalAmt": amount,
                "Line": [{
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Description": "Expense from receipt",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": account_id}
                    }
                }]
            }
        }
        return self._make_request("POST", "bill", data)
