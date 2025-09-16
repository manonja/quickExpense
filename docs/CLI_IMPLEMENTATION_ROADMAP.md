# QuickExpense CLI Implementation Roadmap

## Executive Summary

QuickExpense has a fully functional REST API with OAuth, AI receipt processing, and QuickBooks integration. However, **there is NO CLI interface** - the core promise of the MVP. Anton needs CLI commands (`quickexpense upload` and `quickexpense bulk`) to process his 1000+ receipts.

## Current State Analysis

### ✅ What's Built and Working

1. **Backend Infrastructure**
   - FastAPI REST API with all required endpoints
   - Full QuickBooks integration with OAuth token management
   - Automatic token refresh functionality
   - JSON file-based token storage (`data/tokens.json`)

2. **Receipt Processing**
   - Gemini AI integration for receipt extraction
   - `POST /api/v1/receipts/extract` endpoint working
   - Supports JPEG, PNG, GIF, BMP, WebP formats
   - Returns structured data with vendor, amount, date, items

3. **Expense Creation**
   - `POST /api/v1/expenses` creates expenses in QuickBooks
   - Automatic vendor lookup and creation
   - Proper expense categorization
   - Full error handling

4. **Development Infrastructure**
   - Python 3.12 with full type safety
   - Comprehensive test structure
   - Pre-commit hooks and linting
   - Modern project structure

### ❌ What's Missing for MVP

1. **No CLI Interface**
   - No `quickexpense` command exists
   - No way to run from terminal
   - No console entry point configured

2. **No File Processing**
   - Can't read JPEG files from disk
   - No bulk directory processing
   - No progress tracking

3. **No User Interaction**
   - No --dry-run mode
   - No --interactive mode
   - No output formatting options

## Gap Analysis

| MVP Promise | Current State | Gap |
|-------------|---------------|-----|
| `quickexpense upload receipt.jpeg` | REST API exists | Need CLI wrapper |
| `quickexpense bulk ./receipts/` | API handles single files | Need directory scanner |
| Process 1000s of receipts | API is stateless | Need progress tracking |
| --dry-run flag | API always creates expenses | Need preview mode |
| --interactive mode | API is non-interactive | Need user prompts |
| Terminal-based workflow | Web API only | Need CLI interface |

## Implementation Plan

### Phase 1: CLI Foundation (Critical Path - 2-3 days)

#### 1.1 Create CLI Entry Point
```python
# src/quickexpense/cli.py
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='QuickExpense CLI')
    subparsers = parser.add_subparsers(dest='command')

    # Upload command
    upload_parser = subparsers.add_parser('upload')
    upload_parser.add_argument('receipt', type=Path)
    upload_parser.add_argument('--dry-run', action='store_true')

    # Bulk command
    bulk_parser = subparsers.add_parser('bulk')
    bulk_parser.add_argument('directory', type=Path)
    bulk_parser.add_argument('--dry-run', action='store_true')
    bulk_parser.add_argument('--interactive', action='store_true')
```

#### 1.2 Add Console Script to pyproject.toml
```toml
[project.scripts]
quickexpense = "quickexpense.cli:main"
```

#### 1.3 Implement Single Upload
- Read JPEG file from filesystem
- Convert to base64
- Call existing API client (reuse services)
- Display results
- Create expense if not --dry-run

#### 1.4 Implement Bulk Processing
- Scan directory for JPEG files
- Process sequentially with progress bar
- Collect results and errors
- Display summary report

### Phase 2: Essential Features (1-2 days)

#### 2.1 --dry-run Implementation
- Extract and display without creating expenses
- Show JSON output for verification
- Critical for testing 1000+ receipts

#### 2.2 --interactive Mode
- Display each receipt's extracted data
- Prompt: "Create expense? [Y/n/skip/edit]"
- Allow manual corrections
- Essential for handling edge cases

### Phase 3: Production Readiness (2-3 days)

#### 3.1 Error Handling
- Graceful handling of failed extractions
- Continue processing on errors
- Log failures to `failed_receipts.log`
- Retry logic for API failures

#### 3.2 Progress Tracking
- Progress bar for bulk operations
- Save state for resume capability
- `receipts_processed.json` checkpoint file

#### 3.3 Output Options
- `--output json` for scripting
- `--output csv` for Excel review
- `--quiet` for automation
- Summary statistics

### Phase 4: Polish & Performance (1-2 days)

#### 4.1 Authentication Flow
- Check token validity on startup
- Prompt to run OAuth if expired
- Clear error messages

#### 4.2 Performance
- Concurrent processing (with rate limiting)
- Batch API calls where possible
- Memory-efficient for large directories

## Technical Approach

### 1. Reuse Existing Code
```python
# Don't rebuild - wrap existing services
from quickexpense.services.quickbooks import QuickBooksService
from quickexpense.services.gemini import GeminiService
from quickexpense.models import ReceiptExtractionRequest

# CLI just orchestrates existing functionality
async def process_receipt(file_path: Path, qb_service, gemini_service):
    image_data = base64.b64encode(file_path.read_bytes())
    receipt = await gemini_service.extract_receipt_data(image_data)
    if not dry_run:
        expense = await qb_service.create_expense(receipt.to_expense())
    return expense
```

### 2. Start Simple
- Synchronous implementation first
- Add async/concurrent later
- Focus on reliability over speed

### 3. Progressive Enhancement
- Basic CLI → Add flags → Add interactivity → Add performance

## Success Metrics

1. **Functional**: Anton can run `quickexpense bulk ./receipts/`
2. **Reliable**: Processes 1000+ receipts without crashing
3. **Verifiable**: --dry-run lets him check before committing
4. **Resumable**: Can restart failed bulk jobs
5. **Transparent**: Clear progress and error reporting

## Quick Wins

1. **Day 1**: Basic `quickexpense upload receipt.jpg` working
2. **Day 2**: `quickexpense bulk ./receipts/` with progress
3. **Day 3**: --dry-run flag functional
4. **Day 4**: Error handling and resume capability
5. **Day 5**: Polish and documentation

## Dependencies & Risks

### Dependencies
- Click or argparse (already in Python stdlib)
- Rich for progress bars (optional)
- Existing API must remain stable

### Risks
- API rate limits when processing 1000s of receipts
- Memory usage with large directories
- Token expiry during long bulk runs

### Mitigations
- Implement exponential backoff
- Process in chunks
- Refresh tokens proactively

## Next Immediate Steps

1. Create `src/quickexpense/cli.py`
2. Add console_scripts to `pyproject.toml`
3. Implement basic upload command
4. Test with single receipt
5. Add bulk processing
6. Deploy to Anton for testing

## Conclusion

The API layer is complete and robust. The missing piece is a thin CLI wrapper that:
- Reads files from disk
- Calls existing API endpoints
- Displays progress and results
- Handles bulk operations

With 5-7 days of focused development, Anton will have a working CLI to process his 1000+ receipts.
