# QuickBooks Receipt Scanner

FastAPI application that converts receipt data into QuickBooks expenses automatically.

## 🎯 What It Does

Transforms receipt information (vendor, amount, date) into QuickBooks bills through REST API endpoints.

## 📋 Prerequisites

- Python 3.12+
- QuickBooks Developer Account
- QuickBooks Sandbox Company

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get QuickBooks Credentials
1. Go to [QuickBooks Developer Dashboard](https://developer.intuit.com/app/developer/dashboard)
2. Create/select your app
3. Copy Client ID and Client Secret
4. Add redirect URI: `http://localhost:8000/api/quickbooks/callback`

### 3. Configure OAuth
```bash
# Update oauth_setup.py with your credentials
CLIENT_ID = "your_client_id_here"
CLIENT_SECRET = "your_client_secret_here"

# Run OAuth setup
python oauth_setup.py
```

### 4. Start Application
```bash
python main.py
```

## 🔄 System Flow

**Receipt to QuickBooks Expense Process:**

1. **User** → Submit receipt data (vendor, amount, date)
2. **FastAPI App** → Search for vendor in QuickBooks
3. **If vendor not found** → Create new vendor
4. **FastAPI App** → Get expense accounts from QuickBooks
5. **FastAPI App** → Create purchase expense in QuickBooks
6. **QuickBooks** → Return purchase ID and confirmation
7. **User** → Receive success response with expense details

## 🏗 Architecture

**System Components:**
- **Receipt Input** → FastAPI Application
- **FastAPI App** → QuickBooks Client (API Wrapper)
- **QuickBooks Client** → QuickBooks REST API v3
- **OAuth Setup** → Bearer Token → QuickBooks Authentication

**Data Processing:**
- Vendor Search/Create
- Expense Account Lookup  
- Purchase Expense Creation

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint with basic info |
| `/help` | GET | **Display all curl commands** |
| `/test-connection` | GET | Verify QB connection |
| `/vendors/{name}` | GET | Search vendor by name |
| `/vendors` | POST | Create new vendor |
| `/accounts/expense` | GET | Get expense accounts |
| `/expenses` | POST | Create expense from receipt |

## 📝 Receipt Expense Flow - Complete Examples

### Step 1: Get Help (All Commands)
```bash
curl http://localhost:8000/help
```

### Step 2: Test Connection
```bash
curl http://localhost:8000/test-connection
```

### Step 3: Create Expense from Receipt
```bash
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "2024-01-15"
  }'
```

### Direct QuickBooks API Examples (What Happens Behind the Scenes)

#### Query for Existing Vendor
```bash
curl -X GET "https://sandbox-quickbooks.api.intuit.com/v3/company/YOUR_COMPANY_ID/query?query=SELECT * FROM Vendor WHERE Name = 'Office Depot'" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Accept: application/json"
```

#### Create New Vendor (if not found)
```bash
curl -X POST "https://sandbox-quickbooks.api.intuit.com/v3/company/YOUR_COMPANY_ID/vendor" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "Vendor": {
      "Name": "Office Depot",
      "CompanyName": "Office Depot Inc.",
      "BillAddr": {
        "Line1": "123 Business St",
        "City": "Business City",
        "Country": "USA",
        "PostalCode": "12345"
      }
    }
  }'
```

#### Get Expense Accounts
```bash
curl -X GET "https://sandbox-quickbooks.api.intuit.com/v3/company/YOUR_COMPANY_ID/query?query=SELECT * FROM Account WHERE AccountType = 'Expense'" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Accept: application/json"
```

#### Create Expense (Final Step)
```bash
curl -X POST "https://sandbox-quickbooks.api.intuit.com/v3/company/YOUR_COMPANY_ID/purchase" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "Purchase": {
      "AccountRef": {
        "value": "EXPENSE_ACCOUNT_ID",
        "name": "Office Supplies"
      },
      "PaymentType": "Cash",
      "EntityRef": {
        "value": "VENDOR_ID",
        "name": "Office Depot"
      },
      "TotalAmt": 45.67,
      "PurchaseEx": {
        "any": [
          {
            "name": "{http://schema.intuit.com/finance/v3}NameValue",
            "declaredType": "com.intuit.schema.finance.v3.NameValue",
            "scope": "javax.xml.bind.JAXBElement$GlobalScope",
            "value": {
              "Name": "TxnDate",
              "Value": "2023-12-01"
            }
          }
        ]
      },
      "Line": [
        {
          "Amount": 42.25,
          "DetailType": "AccountBasedExpenseLineDetail",
          "AccountBasedExpenseLineDetail": {
            "AccountRef": {
              "value": "EXPENSE_ACCOUNT_ID",
              "name": "Office Supplies"
            }
          }
        },
        {
          "Amount": 3.42,
          "DetailType": "AccountBasedExpenseLineDetail", 
          "AccountBasedExpenseLineDetail": {
            "AccountRef": {
              "value": "TAX_ACCOUNT_ID",
              "name": "Sales Tax"
            }
          }
        }
      ]
    }
  }'
```

## 🔧 Configuration

Environment variables in `.env`:
- `QB_ACCESS_TOKEN` - OAuth bearer token (1 hour expiry)
- `QB_COMPANY_ID` - QuickBooks company identifier
- `QB_BASE_URL` - Sandbox: `https://sandbox-quickbooks.api.intuit.com`

## 🔄 Token Refresh

Access tokens expire every hour. Re-run `python oauth_setup.py` to get fresh tokens.

## 📊 Data Processing Logic

**Receipt Processing Decision Tree:**

1. **Receipt Input** → Extract vendor_name, amount, date
2. **Check Vendor** → Does vendor exist in QuickBooks?
   - **YES** → Use existing vendor ID
   - **NO** → Create new vendor → Get new vendor ID
3. **Get Expense Account** → Fetch available expense accounts
4. **Create Purchase** → Generate QuickBooks expense with vendor + account + tax
5. **Return Result** → Purchase ID and success confirmation

## 🛠 Troubleshooting

- **"ModuleNotFoundError"**: Run `pip install -r requirements.txt`
- **"401 Unauthorized"**: Token expired, re-run OAuth setup
- **"Connection failed"**: Check QB credentials in `.env`

## 📁 Project Structure

```
├── main.py              # FastAPI application
├── quickbooks_client.py # QB API wrapper
├── models.py           # Data models
├── config.py           # Configuration
├── oauth_setup.py      # OAuth helper
└── requirements.txt    # Dependencies
```