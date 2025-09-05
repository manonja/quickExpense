#!/bin/bash
# QuickBooks API Testing Script

echo "🧪 QuickBooks API Testing Script"
echo "================================"

# Base URL
BASE_URL="http://localhost:8000"

# Test 1: Health Check
echo -e "\n1️⃣ Testing Health Check..."
curl -s $BASE_URL/health | jq .

# Test 2: Ready Check
echo -e "\n2️⃣ Testing Ready Check (QuickBooks connection)..."
curl -s $BASE_URL/ready | jq .

# Test 3: Test QuickBooks Connection
echo -e "\n3️⃣ Testing QuickBooks Connection..."
curl -s $BASE_URL/api/v1/test-connection | jq .

# Test 4: Create a Vendor
echo -e "\n4️⃣ Creating a new vendor..."
VENDOR_NAME="Test Vendor $(date +%s)"
echo "Vendor name: $VENDOR_NAME"
VENDOR_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/vendors?vendor_name=$VENDOR_NAME")
echo "$VENDOR_RESPONSE" | jq .
VENDOR_ID=$(echo "$VENDOR_RESPONSE" | jq -r '.id')
echo "Created vendor with ID: $VENDOR_ID"

# Test 5: Search for the vendor
echo -e "\n5️⃣ Searching for vendor..."
curl -s "$BASE_URL/api/v1/vendors/$VENDOR_NAME" | jq .

# Test 6: List expense accounts
echo -e "\n6️⃣ Listing expense accounts..."
curl -s "$BASE_URL/api/v1/accounts/expense" | jq '.[:3]' # Show first 3

# Test 7: Create an expense
echo -e "\n7️⃣ Creating an expense..."
EXPENSE_DATA='{
  "vendor_name": "'"$VENDOR_NAME"'",
  "amount": 123.45,
  "date": "'"$(date +%Y-%m-%d)"'",
  "currency": "USD",
  "category": "Office Supplies",
  "tax_amount": 10.25,
  "description": "Test expense from API"
}'

echo "Expense data:"
echo "$EXPENSE_DATA" | jq .

EXPENSE_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "$EXPENSE_DATA" \
  "$BASE_URL/api/v1/expenses")

echo -e "\nExpense response:"
echo "$EXPENSE_RESPONSE" | jq .

# Extract Purchase ID if successful
if echo "$EXPENSE_RESPONSE" | jq -e '.status == "success"' > /dev/null; then
  PURCHASE_ID=$(echo "$EXPENSE_RESPONSE" | jq -r '.data.Purchase.Id')
  echo -e "\n✅ Success! Created expense with QuickBooks Purchase ID: $PURCHASE_ID"
  echo "Check your QuickBooks sandbox to see the new expense!"
else
  echo -e "\n❌ Failed to create expense"
fi
