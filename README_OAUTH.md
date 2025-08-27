# 🚀 Simple QuickBooks OAuth Setup

Get your bearer token for API testing in 3 easy steps!

## 📋 Prerequisites

1. **QuickBooks Developer Account**: [Sign up here](https://developer.intuit.com/app/developer/dashboard)
2. **Create an App** in the developer dashboard
3. **Get your credentials**: Client ID and Client Secret

## 🔧 Setup Steps

### Step 1: Configure Your App
1. Open `oauth_setup.py`
2. Replace these values:
   ```python
   CLIENT_ID = "YOUR_CLIENT_ID_HERE"        # From QB developer dashboard
   CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE" # From QB developer dashboard
   ```

### Step 2: Set Redirect URI
In your QuickBooks app settings, add this redirect URI:
```
http://localhost:8000/api/quickbooks/callback
```

### Step 3: Run OAuth Setup
```bash
python oauth_setup.py
```

That's it! The browser will open, you'll connect to QuickBooks, and your `.env` file will be created automatically.

## 🧪 Testing Your Setup

install dependencies:
```bash
pip install -r requirements.txt
```

Once you have your tokens, test your FastAPI app:

```bash
# Start your app
python main.py

# Test the connection
curl http://localhost:8000/test-connection

# Test creating an expense
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test Vendor",
    "amount": 25.50,
    "date": "2024-01-15"
  }'
```

## 🔑 Your Bearer Token

After OAuth setup, your bearer token will be in `.env` as `QB_ACCESS_TOKEN`.

For manual API testing:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  https://sandbox-quickbooks.api.intuit.com/v3/company/YOUR_COMPANY_ID/companyinfo/YOUR_COMPANY_ID
```

## ⏰ Token Expiration

- **Access Token**: Expires in 1 hour
- **Refresh Token**: Expires in 101 days
- The OAuth setup gets both tokens automatically

## 🛠 Troubleshooting

**"Missing CLIENT_ID"**: Update the credentials in `oauth_setup.py`

**"Redirect URI mismatch"**: Make sure your QB app has `http://localhost:8000/api/quickbooks/callback` as a redirect URI

**"Connection failed"**: Check your `.env` file has all the required variables

**"401 Unauthorized"**: Your access token expired (1 hour limit) - run OAuth setup again

## 📁 Files Created

- `.env` - Your API credentials and tokens
- This setup works with your existing FastAPI app without any changes needed!
