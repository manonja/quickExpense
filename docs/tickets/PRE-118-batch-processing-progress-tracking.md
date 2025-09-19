# PRE-118: Intelligent Batch Processing with Progress Tracking

**Type:** Enhancement
**Priority:** Medium (User Productivity)
**Effort:** 3 Story Points
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** busy sole proprietor with multiple receipts from business trips
**I want** to upload a folder of receipts and have them processed automatically
**So that** I can efficiently handle expense entry without processing receipts one by one

## Business Value
- **Problem:** Current system only processes single receipts, creating tedious workflow for multiple expenses
- **Impact:** Time-consuming manual work, prone to missing receipts, poor user experience
- **Solution:** Intelligent batch processing with progress tracking, error recovery, and comprehensive reporting

## Description
Implement comprehensive batch processing capabilities that can scan folders recursively, process multiple receipt types, provide real-time progress feedback, handle errors gracefully, and generate detailed summary reports. The system should be efficient, reliable, and provide excellent user experience for high-volume processing.

## Batch Processing Requirements
**User Scenarios:**
- Business trip with 20+ receipts (hotels, meals, transportation)
- Monthly expense processing (mix of PDF and image receipts)
- Year-end accounting preparation (hundreds of receipts)
- Recovered files from phone backup (various formats)
- Mixed provincial receipts (cross-Canada travel)

## Acceptance Criteria

### AC1: Folder Scanning and File Discovery
- [ ] Scan folders recursively for supported file formats
- [ ] Support file pattern filtering (*.pdf, *.jpg, etc.)
- [ ] Detect and skip duplicate files based on content hash
- [ ] Handle large directories efficiently (1000+ files)
- [ ] Support both absolute and relative paths
- [ ] Validate file accessibility before processing

### AC2: Progress Tracking and User Feedback
- [ ] Real-time progress bar with current file and completion percentage
- [ ] Estimated time remaining based on processing speed
- [ ] Live status updates (extracting, categorizing, submitting)
- [ ] Summary statistics (processed, successful, failed, skipped)
- [ ] Graceful handling of terminal resize and interruption
- [ ] Optional quiet mode for automated processing

### AC3: Error Handling and Recovery
- [ ] Continue processing on individual file failures
- [ ] Detailed error reporting with actionable suggestions
- [ ] Retry logic for transient failures (network, API limits)
- [ ] Skip corrupted or unsupported files gracefully
- [ ] Preserve partial results for failed batches
- [ ] Support resume functionality for interrupted batches

### AC4: Comprehensive Reporting
- [ ] Detailed summary report after batch completion
- [ ] Success/failure breakdown with specific error messages
- [ ] Financial summary (total amounts, tax calculations)
- [ ] Export results to CSV for accounting review
- [ ] QuickBooks entry IDs for successful submissions
- [ ] Processing performance metrics

### AC5: Advanced Batch Options
- [ ] Dry-run mode for preview without QB submission
- [ ] Selective processing based on date ranges or amounts
- [ ] Custom business context for entire batch
- [ ] Parallel processing for improved performance
- [ ] Batch size limits to prevent system overload

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/services/batch_processor.py` - New batch processing service
- `src/quickexpense/services/file_scanner.py` - File discovery and validation
- `src/quickexpense/services/progress_tracker.py` - Progress monitoring
- `src/quickexpense/cli.py` - New batch commands
- `tests/services/test_batch_processor.py` - Comprehensive tests

### BatchProcessor Service
```python
class BatchProcessor:
    """Intelligent batch processing with progress tracking."""

    def __init__(
        self,
        expense_processor: ExpenseProcessor,
        audit_logger: AuditLogger,
        progress_tracker: ProgressTracker
    ):
        self.expense_processor = expense_processor
        self.audit_logger = audit_logger
        self.progress_tracker = progress_tracker
        self.file_scanner = FileScanner()

    async def process_batch(
        self,
        folder_path: str,
        options: BatchProcessingOptions
    ) -> BatchProcessingResult:
        """Process multiple receipts in batch."""

        batch_id = self._generate_batch_id()

        try:
            # 1. Scan and validate files
            files = await self.file_scanner.scan_folder(
                folder_path,
                options.pattern,
                options.recursive
            )

            self.progress_tracker.initialize(
                total_files=len(files),
                batch_id=batch_id
            )

            # 2. Filter and deduplicate
            files = await self._filter_and_deduplicate(files, options)

            # 3. Process files with progress tracking
            results = []
            for i, file_path in enumerate(files):
                if self.progress_tracker.should_stop:
                    break

                self.progress_tracker.update_current_file(file_path, i + 1)

                try:
                    result = await self._process_single_file(
                        file_path, options, batch_id
                    )
                    results.append(result)

                except Exception as e:
                    error_result = self._create_error_result(file_path, e)
                    results.append(error_result)

                    if not options.continue_on_error:
                        break

            # 4. Generate comprehensive report
            batch_result = self._generate_batch_result(
                batch_id, results, options
            )

            # 5. Export results if requested
            if options.export_path:
                await self._export_results(batch_result, options.export_path)

            return batch_result

        except Exception as e:
            self.audit_logger.log_batch_error(batch_id, str(e))
            raise BatchProcessingError(f"Batch processing failed: {e}") from e

    async def _process_single_file(
        self,
        file_path: str,
        options: BatchProcessingOptions,
        batch_id: str
    ) -> FileProcessingResult:
        """Process single file with error handling."""

        correlation_id = f"{batch_id}_file_{Path(file_path).stem}"

        start_time = time.time()

        try:
            # Process with existing expense processor
            result = await self.expense_processor.process_receipt_file(
                file_path,
                dry_run=options.dry_run,
                business_context=options.business_context,
                correlation_id=correlation_id
            )

            processing_time = time.time() - start_time

            return FileProcessingResult(
                file_path=file_path,
                success=True,
                processing_time=processing_time,
                vendor_name=result.vendor_name,
                total_amount=result.total_amount,
                qb_entry_ids=result.qb_entry_ids,
                correlation_id=correlation_id
            )

        except Exception as e:
            processing_time = time.time() - start_time

            return FileProcessingResult(
                file_path=file_path,
                success=False,
                processing_time=processing_time,
                error=str(e),
                correlation_id=correlation_id
            )

class FileScanner:
    """Efficient file scanning and validation."""

    SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    async def scan_folder(
        self,
        folder_path: str,
        pattern: str | None = None,
        recursive: bool = True
    ) -> list[str]:
        """Scan folder for supported receipt files."""

        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Invalid folder path: {folder_path}")

        files = []

        if recursive:
            search_pattern = "**/*" if not pattern else f"**/{pattern}"
        else:
            search_pattern = "*" if not pattern else pattern

        for file_path in folder.glob(search_pattern):
            if (file_path.is_file() and
                file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS):
                files.append(str(file_path))

        return sorted(files)

    async def calculate_file_hash(self, file_path: str) -> str:
        """Calculate content hash for duplicate detection."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

class ProgressTracker:
    """Real-time progress tracking with rich console output."""

    def __init__(self):
        self.console = Console()
        self.progress = None
        self.task_id = None
        self.should_stop = False
        self.start_time = None

    def initialize(self, total_files: int, batch_id: str):
        """Initialize progress tracking."""
        self.start_time = time.time()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            TimeElapsedColumn(),
            "•",
            TimeRemainingColumn(),
            console=self.console
        )

        self.task_id = self.progress.add_task(
            f"Processing batch {batch_id}",
            total=total_files
        )

        self.progress.start()

    def update_current_file(self, file_path: str, current_index: int):
        """Update progress with current file."""
        file_name = Path(file_path).name
        self.progress.update(
            self.task_id,
            advance=1,
            description=f"Processing: {file_name}"
        )

    def complete(self):
        """Complete progress tracking."""
        if self.progress:
            self.progress.stop()
```

### CLI Integration
```bash
# New batch processing commands
quickexpense batch /path/to/receipts
quickexpense batch /path/to/receipts --recursive --pattern "*.pdf"
quickexpense batch /path/to/receipts --dry-run --export results.csv
quickexpense batch /path/to/receipts --continue-on-error --parallel 3
quickexpense batch /path/to/receipts --business-context "Q4 business trip"

# Advanced options
quickexpense batch /path/to/receipts --date-range "2025-09-01:2025-09-30"
quickexpense batch /path/to/receipts --min-amount 10 --max-amount 1000
quickexpense batch /path/to/receipts --resume batch_20250919_142355
```

### Models
```python
class BatchProcessingOptions(BaseModel):
    """Batch processing configuration."""

    recursive: bool = True
    pattern: str | None = None
    continue_on_error: bool = True
    dry_run: bool = False
    parallel_workers: int = 1
    business_context: dict | None = None
    export_path: str | None = None
    date_range: tuple[date, date] | None = None
    amount_range: tuple[Decimal, Decimal] | None = None

class FileProcessingResult(BaseModel):
    """Individual file processing result."""

    file_path: str
    success: bool
    processing_time: float
    vendor_name: str | None = None
    total_amount: Decimal | None = None
    qb_entry_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    correlation_id: str | None = None

class BatchProcessingResult(BaseModel):
    """Complete batch processing result."""

    batch_id: str
    total_files: int
    successful: int
    failed: int
    skipped: int
    total_processing_time: float
    total_amount_processed: Decimal
    results: list[FileProcessingResult]
    summary_report: dict[str, Any]
```

## Testing Requirements

### Unit Tests
- [ ] Test file scanning with various folder structures
- [ ] Test duplicate detection and filtering
- [ ] Test progress tracking and user feedback
- [ ] Test error handling and recovery
- [ ] Test batch result generation and export

### Integration Tests
- [ ] Test end-to-end batch processing with mixed file types
- [ ] Test large batch processing (100+ files)
- [ ] Test error scenarios and recovery
- [ ] Test CLI commands and output formatting
- [ ] Test performance with parallel processing

### Performance Tests
```python
# Batch Processing Performance Tests
PERFORMANCE_TEST_SCENARIOS = {
    "small_batch": {
        "file_count": 10,
        "target_time": 60,  # seconds
        "target_throughput": 0.17  # files per second
    },
    "medium_batch": {
        "file_count": 50,
        "target_time": 180,  # 3 minutes
        "target_throughput": 0.28
    },
    "large_batch": {
        "file_count": 200,
        "target_time": 600,  # 10 minutes
        "target_throughput": 0.33
    }
}
```

## Dependencies
- Existing expense processor ✅ Completed
- Audit logging system (PRE-117) - Concurrent development
- CLI interface ✅ Completed

## Definition of Done
- [ ] Folder scanning with recursive support and pattern filtering
- [ ] Real-time progress tracking with rich console output
- [ ] Error handling with continue-on-error capability
- [ ] Comprehensive batch reporting and CSV export
- [ ] Dry-run mode for safe testing
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate batch workflows
- [ ] Performance tests meet throughput targets
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)

## Validation Scenarios

### Scenario 1: Business Trip Expense Processing
**Given** folder with 25 mixed receipts from 5-day business trip
**When** running batch processing with recursive scan
**Then**
- All supported file types processed automatically
- Progress bar shows real-time status
- Provincial tax calculations applied correctly
- Summary report shows breakdown by category
- CSV export ready for accountant review
- Total processing time under 5 minutes

### Scenario 2: Error Recovery and Continuation
**Given** batch with 3 corrupted files among 20 valid receipts
**When** processing with continue-on-error enabled
**Then**
- Corrupted files skipped with clear error messages
- Valid receipts processed successfully
- Final report shows 17 successful, 3 failed
- QuickBooks entries created for successful files
- Detailed error log available for troubleshooting

### Scenario 3: Large Volume Processing
**Given** 200 receipts from quarterly business activities
**When** processing with parallel workers enabled
**Then**
- Processing completes within 10 minutes
- Memory usage remains stable throughout
- Progress tracking provides accurate time estimates
- No duplicate entries created in QuickBooks
- Comprehensive financial summary generated

## Risk Mitigation
- **Memory Usage:** Stream processing and batch size limits
- **API Rate Limits:** Built-in throttling and retry logic
- **File System Performance:** Efficient scanning algorithms
- **User Experience:** Interruptible processing with resume capability

## Success Metrics
- Process 50 receipts in under 3 minutes
- <2% failure rate for valid receipt files
- Memory usage remains under 500MB for any batch size
- User satisfaction >4.5/5 for batch processing experience
- 90% reduction in time for multi-receipt processing
