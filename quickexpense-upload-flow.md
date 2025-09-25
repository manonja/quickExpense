# QuickExpense Upload Command Execution Flow

This document explains the exact execution flow when running:
```bash
uv run quickexpense upload /Users/manonjacquin/Documents/receipts/IMG_7597.HEIC --verbose
```

## 1. Command Entry Point

### 1.1 UV Package Manager Execution
- **Program**: `uv` (Rust-based Python package manager)
- **Action**: Resolves the `quickexpense` script from `pyproject.toml`
- **Location**: `pyproject.toml:24-25`
  ```toml
  [project.scripts]
  quickexpense = "quickexpense.cli:main"
  ```

### 1.2 CLI Module Initialization
- **Module**: `src/quickexpense/cli.py`
- **Function**: `main()` (line 1180)
- **Action**: Calls `asyncio.run(async_main())`

## 2. Argument Parsing

### 2.1 Parser Creation
- **Function**: `create_parser()` (line 1079)
- **Action**: Creates ArgumentParser with subcommands (auth, status, upload)
- **Upload Parser**: Configured with:
  - `receipt` (required): File path argument
  - `--verbose`: Boolean flag for detailed output
  - `--dry-run`: Preview mode
  - `--output`: Format (text/json)

### 2.2 Command Dispatch
- **Function**: `async_main()` (line 1163)
- **Command**: `upload` detected from args
- **Route**: Calls `cli.upload_command(args)`

## 3. CLI Application Initialization

### 3.1 QuickExpenseCLI Constructor
- **Class**: `QuickExpenseCLI` (line 71)
- **Initialization**:
  - Loads settings via `get_settings()`
  - Initializes services to None (lazy loading)
  - Sets up audit logging with `AuditLogger`

### 3.2 File Validation
- **Function**: `validate_file()` (line 229)
- **Checks**:
  - File exists and is readable
  - File extension in supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.pdf`
  - File size ≤ 10MB
  - Read permissions

## 4. Service Initialization

### 4.1 Authentication & Token Management
- **Function**: `initialize_services()` (line 179)
- **Token Loading**: `_load_and_validate_tokens()` (line 88)
  - Uses `TokenStore` to load from `data/tokens.json`
  - Validates token presence and company_id
- **OAuth Manager**: `_create_oauth_manager()` (line 106)
  - Creates `QuickBooksOAuthManager` with token refresh capability
  - Sets up token save callbacks

### 4.2 Service Dependencies
- **Gemini Service**: `GeminiService(settings)` - AI receipt processing
- **QuickBooks Client**: `QuickBooksClient()` - API communication
- **QuickBooks Service**: `QuickBooksService(client)` - Business logic layer
- **Business Rules Engine**: `BusinessRuleEngine(config_path)` - Categorization rules

## 5. Receipt Processing Pipeline

### 5.1 Audit Trail Initialization
- **Function**: `process_receipt()` (line 539)
- **Audit Logger**: Creates correlation ID for tracking
- **Verbose Mode**: Displays correlation ID and audit log path

### 5.2 Receipt Data Extraction
- **Function**: `_extract_receipt_data()` (line 258)
- **Process**:
  1. Reads file content as binary
  2. Base64 encodes the image data
  3. Creates `ReceiptExtractionRequest`
  4. Calls `GeminiService.extract_receipt_data()`

#### 5.2.1 Gemini AI Processing
- **Service**: `GeminiService` in `src/quickexpense/services/gemini.py`
- **Model**: Google Generative AI with JSON schema response
- **File Processing**: Handles HEIC/images via `FileProcessorService`
- **Returns**: `ExtractedReceipt` model with vendor, amount, date, line items

### 5.3 Business Rules Application
- **Function**: `_apply_business_rules()` (line 316)
- **Engine**: `BusinessRuleEngine` with Canadian tax compliance
- **Process**:
  1. Creates `ExpenseContext` from receipt data
  2. Runs categorization rules on line items
  3. Returns categorized line items with confidence scores
  4. Applies deductibility percentages per CRA rules

#### 5.3.1 Business Rules Engine
- **Service**: `BusinessRuleEngine` in `src/quickexpense/services/business_rules.py`
- **Config**: Loads from `config/business_rules.json`
- **Features**:
  - Vendor-aware categorization
  - Provincial tax awareness
  - T2125 tax form mapping
  - CRA ITA Section 67.1 compliance

### 5.4 QuickBooks Integration
- **Function**: `_create_quickbooks_expense()` (line 508)
- **Service**: `QuickBooksService` creates Purchase record
- **Process**:
  1. Converts enhanced expense to QuickBooks `Expense` model
  2. Makes API call to create Purchase entry
  3. Returns QuickBooks response with Purchase ID

#### 5.4.1 QuickBooks Service
- **Service**: `QuickBooksService` in `src/quickexpense/services/quickbooks.py`
- **Client**: `QuickBooksClient` with OAuth token management
- **API**: Creates Purchase entries via QuickBooks Online API

## 6. Audit Logging (Verbose Mode)

### 6.1 Structured Logging
- **Service**: `AuditLogger` in `src/quickexpense/services/audit_logger.py`
- **Format**: JSON structured logs with correlation ID
- **Components Logged**:
  - Gemini AI extraction with confidence scores
  - Business rules application with categorization
  - QuickBooks integration with entry IDs
  - Processing completion with summary

### 6.2 Compliance Features
- **Retention**: 7-year policy for CRA requirements
- **Sanitization**: Sensitive data removal
- **Entity Context**: Sole proprietorship tracking
- **Performance**: Processing time measurements

## 7. Output Generation

### 7.1 Result Structure Creation
- **Function**: `_create_result_structure()` (line 457)
- **Components**:
  - Original receipt data
  - Business rules categorization summary
  - Enhanced expense with line items
  - Tax deductibility calculations

### 7.2 Output Formatting
- **Function**: `format_output()` (line 668)
- **Verbose Mode Sections**:
  - Receipt Data
  - Business Rules Categorization (per line item)
  - Tax Deductibility Summary
  - Enhanced Expense Summary
  - Result message with QuickBooks ID

## 8. Error Handling & Cleanup

### 8.1 Exception Handling
- **File Validation Errors**: Exit code 2
- **API Errors**: Exit code 3 (includes auth failures)
- **General Errors**: Exit code 1
- **Keyboard Interrupt**: Exit code 130

### 8.2 Resource Cleanup
- **Function**: `cleanup()` (line 224)
- **Action**: Closes QuickBooks client HTTP connections
- **Guarantee**: Called in finally block

## 9. Programs and Order Summary

### Execution Order:
1. **UV** → Launches Python script via project.scripts
2. **Python CLI** → Parses arguments and validates file
3. **Service Initialization** → Loads tokens, creates API clients
4. **Gemini AI** → Extracts receipt data from HEIC file
5. **Business Rules Engine** → Categorizes expenses with Canadian tax rules
6. **QuickBooks API** → Creates Purchase entry
7. **Audit Logger** → Records structured compliance trail
8. **Output Formatter** → Displays verbose results
9. **Cleanup** → Closes connections and exits

### Key Dependencies:
- **UV**: Package management and script execution
- **Python 3.12**: Runtime with type safety
- **Google Generative AI**: Receipt OCR and data extraction
- **QuickBooks Online API**: Expense creation
- **Pydantic**: Data validation and serialization
- **HTTPX**: Async HTTP client for API calls

### Configuration Files:
- `pyproject.toml`: Project metadata and scripts
- `data/tokens.json`: OAuth tokens storage
- `config/business_rules.json`: Categorization rules
- `.env`: API keys and static configuration

This flow represents a complete pipeline from file upload to QuickBooks expense creation with comprehensive audit logging for Canadian tax compliance.
