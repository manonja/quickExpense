# QuickExpense - Expense Verification Guide

This guide shows you multiple ways to verify that your expenses were successfully created in QuickBooks after processing receipts.

## 📋 Quick Reference

After running `uv run quickexpense upload receipt.jpg`, you'll see:
```
Successfully created expense in QuickBooks (ID: 185)
```

Use any of these methods to verify the expense was created:

## 1. 🔍 Verify Specific Expense by ID

**Best for**: Checking the exact expense you just created

```bash
uv run python scripts/verify_expense.py 185
```

**Example Output**:
```
✅ Found Purchase ID: 185
   Date: 2019-12-20
   Vendor: Harrods
   Total: $153.95
   Payment Type: Cash
   Payment Account: Chequing

   Line Items:
   - $153.95 → Insurance Expense-General Liability Insurance
```

## 2. 🏪 Search by Vendor Name

**Best for**: Finding all expenses for a specific vendor

```bash
uv run python scripts/search_vendor_expenses.py "Harrods"
```

**Example Output**:
```
📊 Expenses for Harrods
============================================================

ID: 185
Date: 2019-12-20
Amount: $153.95
Currency: CAD
Type: Cash
Account: Chequing

============================================================
Total: $153.95
Count: 1 expenses
```

## 3. 📅 List Recent Expenses

**Best for**: Seeing all recent activity

```bash
uv run python scripts/list_recent_expenses.py
```

**Example Output**:
```
📊 Recent Expenses (last 30 days)
============================================================

ID: 185
Date: 2019-12-20
Vendor: Harrods
Amount: $153.95
Type: Cash

============================================================
Total: $153.95
Count: 1 expenses
```

## 4. 🌐 QuickBooks Online Interface

**Best for**: Visual confirmation and detailed expense management

1. Go to [https://sandbox.qbo.intuit.com/](https://sandbox.qbo.intuit.com/)
2. Log in with your Intuit Developer account
3. Navigate to **Expenses** → **Expenses**
4. Look for your expense in the list

## 🛠️ Troubleshooting Verification

### "No authentication tokens found"
```bash
uv run quickexpense auth
```

### "Purchase ID not found"
- Check you're using the correct ID from the CLI output
- The expense might be very old (try searching by vendor)

### "Vendor not found"
- Check spelling of vendor name (case sensitive)
- The vendor might have been created with a slightly different name

### Script errors
Make sure you're in the project directory and have activated the environment:
```bash
cd quickExpense
uv run python scripts/verify_expense.py 185
```

## 📊 Understanding the Data

### Purchase Fields Explained
- **ID**: Unique QuickBooks Purchase ID
- **Date**: Transaction date from receipt
- **Vendor**: Company/store name
- **Total**: Full amount including tax
- **Payment Type**: Usually "Cash" for receipt uploads
- **Payment Account**: Bank or credit card account used
- **Line Items**: Breakdown by expense category/account

### Currency Handling
- Receipts can be in any currency (USD, GBP, EUR, etc.)
- QuickBooks may convert to your company's base currency
- Original and converted amounts are tracked

## 🎯 Best Practices

1. **Always verify important expenses** using the Purchase ID
2. **Use vendor search** to check for duplicates
3. **Check QuickBooks Online** for visual confirmation
4. **Keep receipt files** even after successful upload
5. **Note the Purchase ID** for your records

## 🔧 Advanced Usage

### Custom Date Ranges
```bash
# Last 7 days
uv run python scripts/list_recent_expenses.py 7

# Last year (to find old test expenses)
uv run python scripts/list_recent_expenses.py 365
```

### Batch Verification
If you process multiple receipts, save the IDs and verify them all:
```bash
# Process receipts and note IDs
uv run quickexpense upload receipt1.jpg  # ID: 185
uv run quickexpense upload receipt2.jpg  # ID: 186
uv run quickexpense upload receipt3.jpg  # ID: 187

# Verify all at once
uv run python scripts/verify_expense.py 185
uv run python scripts/verify_expense.py 186
uv run python scripts/verify_expense.py 187
```

With these verification tools, you can be confident that your receipt processing is working correctly and your expenses are properly recorded in QuickBooks! 🎉
