import httpx

from config import settings


class QuickBooksClient:
    def __init__(self):
        self.base_url = settings.qb_base_url
        self.company_id = settings.qb_company_id
        self.headers = {
            "Authorization": f"Bearer {settings.qb_access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
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
        data = {"Vendor": {"Name": vendor_name, "CompanyName": vendor_name}}
        return self._make_request("POST", "vendor", data)

    def get_expense_accounts(self):
        query = "SELECT * FROM Account WHERE AccountType = 'Expense'"
        return self._make_request("GET", f"query?query={query}")

    def create_expense(
        self,
        vendor_id: str,
        vendor_name: str,
        amount: float,
        date: str,
        account_id: str,
        account_name: str = "Office Supplies",
        tax_amount: float = 0.0,
        tax_account_id: str = None,
    ):
        # Calculate base amount (total - tax)
        base_amount = amount - tax_amount

        # Build line items
        line_items = [
            {
                "Amount": base_amount,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": account_id, "name": account_name}
                },
            }
        ]

        # Add tax line if tax amount provided
        if tax_amount > 0 and tax_account_id:
            line_items.append(
                {
                    "Amount": tax_amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": tax_account_id, "name": "Sales Tax"}
                    },
                }
            )

        data = {
            "Purchase": {
                "AccountRef": {"value": account_id, "name": account_name},
                "PaymentType": "Cash",
                "EntityRef": {"value": vendor_id, "name": vendor_name},
                "TotalAmt": amount,
                "PurchaseEx": {
                    "any": [
                        {
                            "name": "{http://schema.intuit.com/finance/v3}NameValue",
                            "declaredType": "com.intuit.schema.finance.v3.NameValue",
                            "scope": "javax.xml.bind.JAXBElement$GlobalScope",
                            "value": {"Name": "TxnDate", "Value": date},
                        }
                    ]
                },
                "Line": line_items,
            }
        }
        return self._make_request("POST", "purchase", data)
