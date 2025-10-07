# API Reference for QuickExpense Docker

## 📡 Overview

This document provides comprehensive API reference for the QuickExpense application running in Docker. The API follows REST principles and provides endpoints for receipt processing, QuickBooks integration, and multi-agent system management.

## 📋 Table of Contents

- [Base Information](#base-information)
- [Authentication](#authentication)
- [Receipt Processing](#receipt-processing)
- [QuickBooks Integration](#quickbooks-integration)
- [System Endpoints](#system-endpoints)
- [Web UI Endpoints](#web-ui-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

---

## 🌐 Base Information

### API Base URL
```
# Local Docker
http://localhost:8000

# Hugging Face Spaces
https://YOUR_USERNAME-quickexpense-app.hf.space
```

### API Version
```
Current Version: v1
Base Path: /api/v1
```

### Content Types
```
Request: application/json, multipart/form-data
Response: application/json
```

### Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "quickexpense"
}
```

---

## 🔐 Authentication

### QuickBooks OAuth Flow

#### 1. Get Authorization URL
```http
GET /api/web/auth-url
```
**Response:**
```json
{
  "authorization_url": "https://appcenter.intuit.com/connect/oauth2?...",
  "state": "random_state_string"
}
```

#### 2. OAuth Callback (Automatic)
```http
GET /api/web/callback?code=AUTH_CODE&state=STATE&realmId=COMPANY_ID
```
**Response:** Redirects to main application with token stored

#### 3. Check Authentication Status
```http
GET /api/web/auth-status
```
**Response:**
```json
{
  "authenticated": true,
  "company_id": "123456789",
  "company_name": "Sample Company",
  "token_expires_at": "2024-02-15T10:30:00Z"
}
```

---

## 🧾 Receipt Processing

### Multi-Agent Receipt Processing (Recommended)

#### Process Receipt File
```http
POST /api/v1/receipts/process-file
Content-Type: multipart/form-data
```

**Parameters:**
- `receipt` (file, required): Receipt file (JPEG, PNG, PDF, HEIC)
- `additional_context` (string, optional): Additional context about the expense

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.jpg" \
  -F "additional_context=Business meal with client"
```

**Response:**
```json
{
  "success": true,
  "overall_confidence": 0.92,
  "vendor_name": "Tim Hortons",
  "transaction_date": "2024-01-15",
  "total_amount": 12.45,
  "subtotal": 11.05,
  "tax_amount": 1.40,
  "currency": "CAD",
  "category": "Meals & Entertainment",
  "deductibility_percentage": 50.0,
  "qb_account": "Meals and Entertainment",
  "ita_section": "ITA 67.1",
  "audit_risk": "low",
  "calculated_gst_hst": 1.40,
  "deductible_amount": 6.23,
  "tax_validation_result": "valid",
  "processing_time": 2.34,
  "consensus_method": "majority",
  "flags_for_review": [],
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "success": true,
      "confidence_score": 0.95,
      "processing_time": 1.2,
      "extracted_data": {
        "vendor_name": "Tim Hortons",
        "total_amount": 12.45,
        "transaction_date": "2024-01-15"
      }
    },
    {
      "agent_name": "CRArulesAgent",
      "success": true,
      "confidence_score": 0.88,
      "processing_time": 0.8,
      "applied_rules": {
        "category": "Meals & Entertainment",
        "deductibility": 50.0,
        "ita_section": "ITA 67.1"
      }
    },
    {
      "agent_name": "TaxCalculatorAgent",
      "success": true,
      "confidence_score": 0.93,
      "processing_time": 0.4,
      "calculations": {
        "calculated_tax": 1.40,
        "deductible_amount": 6.23,
        "validation": "valid"
      }
    }
  ],
  "agent_confidence_scores": {
    "DataExtractionAgent": 0.95,
    "CRArulesAgent": 0.88,
    "TaxCalculatorAgent": 0.93
  },
  "full_data": {
    "line_items": [],
    "payment_method": "Credit Card",
    "merchant_category": "Restaurant"
  }
}
```

### Simple Receipt Extraction

#### Extract Receipt Data (Base64)
```http
POST /api/v1/receipts/extract
Content-Type: application/json
```

**Request Body:**
```json
{
  "image_base64": "base64_encoded_image_data",
  "category": "Travel",
  "additional_context": "Business trip to NYC"
}
```

**Response:**
```json
{
  "receipt": {
    "vendor_name": "Hotel Grande",
    "transaction_date": "2024-01-15",
    "total_amount": 285.67,
    "subtotal": 253.45,
    "tax_amount": 32.22,
    "currency": "CAD",
    "line_items": [
      {
        "description": "Room Charge",
        "amount": 225.00
      },
      {
        "description": "Resort Fee",
        "amount": 28.45
      }
    ]
  },
  "expense_data": {
    "vendor_name": "Hotel Grande",
    "amount": 285.67,
    "date": "2024-01-15",
    "currency": "CAD",
    "category": "Travel",
    "tax_amount": 32.22,
    "description": "Business trip accommodation"
  },
  "processing_time": 1.85
}
```

---

## 📚 QuickBooks Integration

### Expense Management

#### Create Expense in QuickBooks
```http
POST /api/v1/expenses
Content-Type: application/json
```

**Request Body:**
```json
{
  "vendor_name": "Office Depot",
  "amount": 45.99,
  "date": "2024-01-15",
  "currency": "CAD",
  "category": "Office Supplies",
  "tax_amount": 3.42,
  "description": "Office supplies for Q1",
  "payment_account": "Business Checking"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "purchase_id": "184",
    "quickbooks_id": "184",
    "vendor_name": "Office Depot",
    "total_amount": 45.99,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Vendor Management

#### Search for Vendor
```http
GET /api/v1/vendors/{vendor_name}
```

**Response:**
```json
{
  "vendors": [
    {
      "id": "123",
      "name": "Office Depot",
      "display_name": "Office Depot Canada",
      "active": true
    }
  ]
}
```

#### Create Vendor
```http
POST /api/v1/vendors?vendor_name=New%20Vendor%20Name
```

**Response:**
```json
{
  "vendor": {
    "id": "456",
    "name": "New Vendor Name",
    "display_name": "New Vendor Name",
    "active": true
  }
}
```

### Account Management

#### List Expense Accounts
```http
GET /api/v1/accounts/expense
```

**Response:**
```json
{
  "accounts": [
    {
      "id": "789",
      "name": "Meals and Entertainment",
      "account_type": "Expense",
      "active": true
    },
    {
      "id": "790",
      "name": "Travel",
      "account_type": "Expense",
      "active": true
    }
  ]
}
```

### Connection Testing

#### Test QuickBooks Connection
```http
GET /api/v1/test-connection
```

**Response:**
```json
{
  "status": "connected",
  "company_info": {
    "company_name": "Sample Company",
    "company_id": "123456789",
    "country": "CA"
  },
  "token_status": "valid",
  "expires_at": "2024-02-15T10:30:00Z"
}
```

---

## 🖥️ System Endpoints

### API Information
```http
GET /api/v1/
```

**Response:**
```json
{
  "message": "QuickExpense API",
  "version": "1.0.0",
  "docs": "/docs",
  "features": [
    "multi-agent-processing",
    "quickbooks-integration",
    "canadian-tax-compliance",
    "heic-pdf-support"
  ]
}
```

### System Health
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "quickexpense",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Readiness Check
```http
GET /ready
```

**Response:**
```json
{
  "status": "ready",
  "dependencies": {
    "quickbooks": "connected",
    "gemini_ai": "available",
    "together_ai": "available",
    "agents": "initialized"
  }
}
```

---

## 🌐 Web UI Endpoints

### Main Application
```http
GET /
```
Returns the main web application interface (HTML)

### Upload Receipt (Web)
```http
POST /api/web/upload-receipt
Content-Type: multipart/form-data
```

**Parameters:**
- `receipt` (file, required): Receipt file
- `additional_context` (string, optional): Additional context

**Response:** Same as `/api/v1/receipts/process-file`

---

## ❌ Error Handling

### Error Response Format
```json
{
  "detail": "Error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "abc123"
}
```

### Common HTTP Status Codes

#### 400 Bad Request
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "receipt"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

#### 401 Unauthorized
```json
{
  "detail": "QuickBooks authentication required",
  "error_code": "AUTH_REQUIRED"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "amount"],
      "msg": "Amount must be greater than 0",
      "input": -10.50
    }
  ]
}
```

#### 500 Internal Server Error
```json
{
  "detail": "An unexpected error occurred",
  "error_code": "INTERNAL_ERROR",
  "request_id": "abc123"
}
```

### Multi-Agent Processing Errors
```json
{
  "success": false,
  "overall_confidence": 0.0,
  "vendor_name": null,
  "flags_for_review": [
    "All agents failed to process receipt",
    "Invalid file format detected"
  ],
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "success": false,
      "confidence_score": 0.0,
      "error_message": "Unable to detect file type"
    }
  ]
}
```

---

## 🚦 Rate Limiting

### API Rate Limits
- **Receipt Processing**: 10 requests per minute per IP
- **QuickBooks API**: 100 requests per minute per company
- **General API**: 1000 requests per hour per IP

### Rate Limit Headers
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1642248600
```

### Rate Limit Exceeded Response
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

---

## 📝 Examples

### Complete Receipt Processing Workflow

#### 1. Check Authentication
```bash
curl -X GET http://localhost:8000/api/web/auth-status
```

#### 2. Get Authorization URL (if needed)
```bash
curl -X GET http://localhost:8000/api/web/auth-url
```

#### 3. Process Receipt
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.jpg" \
  -F "additional_context=Business meal with client"
```

#### 4. Create Expense (if not auto-created)
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Tim Hortons",
    "amount": 12.45,
    "date": "2024-01-15",
    "currency": "CAD",
    "category": "Meals & Entertainment",
    "tax_amount": 1.40
  }'
```

### Base64 Image Processing

#### Convert Image to Base64
```bash
# Convert image to base64
base64 -i receipt.jpg > receipt.b64

# Process with API
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$(cat receipt.b64)\",
    \"category\": \"Travel\",
    \"additional_context\": \"Business trip to NYC\"
  }"
```

### Batch Processing
```bash
# Process multiple receipts
for receipt in receipts/*.jpg; do
  echo "Processing $receipt..."
  curl -X POST http://localhost:8000/api/v1/receipts/process-file \
    -F "receipt=@$receipt" \
    -F "additional_context=Batch processing" \
    --output "results/$(basename $receipt .jpg).json"
  sleep 1  # Respect rate limits
done
```

### Error Handling Example
```bash
# Process receipt with error handling
response=$(curl -s -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.jpg" \
  -w "%{http_code}")

if [[ "${response: -3}" == "200" ]]; then
  echo "Success: ${response%???}"
else
  echo "Error: HTTP ${response: -3}"
  echo "Response: ${response%???}"
fi
```

---

## 🔗 OpenAPI/Swagger Documentation

### Interactive API Documentation
```
http://localhost:8000/docs
```

### OpenAPI JSON Schema
```
http://localhost:8000/openapi.json
```

### ReDoc Documentation
```
http://localhost:8000/redoc
```

---

## 📚 Related Documentation

- [Docker Usage Guide](./DOCKER_USAGE.md)
- [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)
- [Hugging Face Deployment](./HUGGING_FACE_DEPLOYMENT.md)
- [Dependencies Guide](./DEPENDENCIES.md)
