# PR: Implement Complete CLI Entry Point with Single Receipt Upload

## 🎯 Overview

This PR implements a fully functional CLI for QuickExpense that allows users to upload single receipt images and automatically create expenses in QuickBooks Online. The implementation includes receipt data extraction using Gemini AI, robust error handling, and a seamless user experience.

## ✅ What's Implemented

### Core Features
- **CLI Commands**:
  - `quickexpense upload <receipt>` - Process a receipt and create expense in QuickBooks
  - `quickexpense auth` - Authenticate with QuickBooks OAuth
  - `quickexpense status` - Check system status and connections
  - `quickexpense --version` - Show version information
  - `quickexpense --help` - Display help information

### Technical Improvements
- Fixed QuickBooks Purchase API integration by adding required `AccountRef` field
- Added payment account selection logic (bank accounts preferred, credit cards as fallback)
- Implemented proper OAuth token refresh with automatic retry on 401 errors
- Enhanced error handling with user-friendly messages and clear next steps
- Fixed field mapping between receipt extraction and expense creation

## 🧪 Testing Instructions

### Prerequisites
1. Clone the repository and install dependencies:
   ```bash
   git clone <repo-url>
   cd quickExpense
   uv sync
   ```

2. Set up environment variables in `.env`:
   ```env
   # QuickBooks OAuth (get from Intuit Developer account)
   QB_CLIENT_ID=your_client_id
   QB_CLIENT_SECRET=your_client_secret
   QB_REDIRECT_URI=http://localhost:8000/callback
   QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
   
   # Gemini AI (get from Google AI Studio)
   GEMINI_API_KEY=your_gemini_api_key
   ```

### First-Time Setup
1. Authenticate with QuickBooks:
   ```bash
   uv run quickexpense auth
   ```
   This opens a browser for OAuth authentication. Select a sandbox company.

2. Verify authentication:
   ```bash
   uv run quickexpense status
   ```

### Testing Receipt Upload
1. Test with dry run (no expense created):
   ```bash
   uv run quickexpense upload path/to/receipt.jpg --dry-run
   ```

2. Create actual expense:
   ```bash
   uv run quickexpense upload path/to/receipt.jpg
   ```

3. Get JSON output:
   ```bash
   uv run quickexpense upload path/to/receipt.jpg --output json
   ```

### Verifying Expenses Were Created
1. Verify specific expense by Purchase ID:
   ```bash
   uv run python scripts/verify_expense.py 123
   ```

2. Search expenses by vendor:
   ```bash
   uv run python scripts/search_vendor_expenses.py "Office Depot"
   ```

3. List recent expenses:
   ```bash
   uv run python scripts/list_recent_expenses.py
   ```

4. Check in QuickBooks Online:
   - Login to [QuickBooks Sandbox](https://sandbox.qbo.intuit.com/)
   - Navigate to **Expenses** → **Expenses**

### Supported Image Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- WebP (.webp)

## 📊 Example Output

```bash
$ uv run quickexpense upload receipt.jpg

Extracting data from receipt: receipt.jpg

Creating expense in QuickBooks...

=== Receipt Data ===
File: /path/to/receipt.jpg
Vendor: Harrods
Date: 2019-12-20
Total Amount: $153.95
Tax: $0.0
Currency: GBP

Items:
  - 601 0000947500 Cookshop ($149.0)
  - 601 0003079668 Cookshop ($4.95)

=== Expense Data ===
Category: General
Description: 601 0000947500 Cookshop, 601 0003079668 Cookshop
Payment Account: debit_card

=== Result ===
Successfully created expense in QuickBooks (ID: 184)
```

## 🔧 Key Fixes

1. **QuickBooks API Error**: Fixed "Invalid account type" error by:
   - Adding `AccountRef` field to Purchase API calls
   - Implementing bank/credit card account queries
   - Properly mapping payment accounts

2. **Field Mapping**: Fixed receipt-to-expense field mapping:
   - Changed `transaction_date` to `date`
   - Proper handling of line items and descriptions

3. **Authentication Flow**: Improved user experience:
   - Clear error messages when tokens expire
   - Automatic token refresh attempts
   - Helpful CLI commands for re-authentication

## 🚀 Deployment Notes

- Tokens are stored in `data/tokens.json` (gitignored)
- OAuth tokens refresh automatically when possible
- Sandbox tokens expire frequently; production tokens last longer
- All pre-commit hooks pass (with some acceptable linting exceptions)
- Verification scripts included to confirm expenses were created successfully

## 📝 Related Issues

- Fixes PRE-106: Implement complete CLI entry point with single receipt upload
- Resolves QuickBooks Purchase API integration issues
- Implements all acceptance criteria from the ticket