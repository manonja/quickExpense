# PRE-119: Error Recovery and Checkpoint System

**Type:** Enhancement
**Priority:** Medium (System Reliability)
**Effort:** 2 Story Points
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** sole proprietor processing receipts with limited internet connectivity
**I want** the system to recover from failures without losing expensive processing work
**So that** I don't have to re-pay for Gemini AI processing or lose time on interrupted workflows

## Business Value
- **Problem:** Network outages, API limits, or system crashes cause complete loss of processing progress
- **Impact:** Wasted money on re-processing, poor user experience, lost productivity
- **Solution:** Intelligent checkpoint system that saves expensive operations and enables seamless recovery

## Description
Implement a comprehensive checkpoint and recovery system that saves processing state after expensive operations (Gemini extraction, business rule application), detects incomplete processing, and provides seamless resume capabilities. The system should be transparent to users while providing robust failure recovery.

## Recovery Scenarios
**Common Failure Points:**
- Internet connectivity interruptions during Gemini API calls
- QuickBooks API rate limiting or authentication expires
- System crashes during multi-step processing
- User interruption (Ctrl+C) during long operations
- Gemini API temporary unavailability
- Batch processing interruptions

## Checkpoint Strategy
**Expensive Operations to Checkpoint:**
1. **Gemini Extraction** (highest cost - $0.01-0.10 per receipt)
2. **Business Rules Application** (computed state)
3. **Provincial Tax Calculations** (derived data)
4. **Vendor Analysis** (time-consuming lookups)

**Quick Operations (No Checkpoint):**
- File validation and reading
- QuickBooks entry creation (fast, idempotent)
- CLI output formatting

## Acceptance Criteria

### AC1: Checkpoint Creation and Management
- [ ] Save processing state after expensive Gemini extraction
- [ ] Checkpoint business rules application results
- [ ] Store provincial tax calculations and vendor analysis
- [ ] Include file hash for validation and duplicate detection
- [ ] Add timestamp and processing metadata
- [ ] Implement atomic checkpoint writes (prevent corruption)

### AC2: Recovery Detection and Resume
- [ ] Automatically detect incomplete processing on startup
- [ ] Validate checkpoint integrity before resuming
- [ ] Handle corrupted or incomplete checkpoint files
- [ ] Provide resume capability via CLI flag
- [ ] Show clear messaging about resumed vs fresh processing
- [ ] Skip completed stages and resume from last checkpoint

### AC3: Checkpoint Lifecycle Management
- [ ] Automatic cleanup of old checkpoints (7 days default)
- [ ] Prevent checkpoint accumulation and disk space issues
- [ ] Handle checkpoint conflicts (same file processed multiple times)
- [ ] Support manual checkpoint cleanup commands
- [ ] Validate checkpoint compatibility across system versions

### AC4: User Experience Integration
- [ ] Transparent checkpoint creation (no user action required)
- [ ] Clear messaging when resuming from checkpoint
- [ ] Option to force fresh processing (ignore checkpoints)
- [ ] Progress indication during recovery operations
- [ ] Detailed logging of checkpoint operations

### AC5: Batch Processing Integration
- [ ] Support checkpoints for batch processing operations
- [ ] Resume batch processing from last successful file
- [ ] Handle partial batch failures with recovery
- [ ] Maintain batch context across resume operations

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/services/checkpoint_manager.py` - New checkpoint management
- `src/quickexpense/services/recovery_service.py` - Recovery logic
- `src/quickexpense/cli.py` - Resume functionality and messaging
- `src/quickexpense/services/expense_processor.py` - Checkpoint integration
- `tests/services/test_checkpoint_manager.py` - Comprehensive tests

### CheckpointManager Service
```python
class CheckpointManager:
    """Manage processing checkpoints for recovery."""

    def __init__(self, checkpoint_dir: Path = Path("data/checkpoints")):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_policy = CheckpointCleanupPolicy()

    async def save_checkpoint(
        self,
        file_path: str,
        stage: ProcessingStage,
        data: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """Save processing checkpoint atomically."""

        file_hash = await self._calculate_file_hash(file_path)
        checkpoint_id = self._generate_checkpoint_id(file_path, file_hash)

        checkpoint_data = CheckpointData(
            checkpoint_id=checkpoint_id,
            file_path=file_path,
            file_hash=file_hash,
            stage=stage,
            data=data,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
            system_version=get_system_version(),
            checksum=self._calculate_data_checksum(data)
        )

        # Atomic write to prevent corruption
        temp_path = self.checkpoint_dir / f"{checkpoint_id}.tmp"
        final_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        try:
            with open(temp_path, "w") as f:
                json.dump(checkpoint_data.model_dump(), f, indent=2, default=str)

            # Atomic move to final location
            temp_path.rename(final_path)

            logger.info(f"Checkpoint saved: {checkpoint_id} at stage {stage}")
            return checkpoint_id

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise CheckpointError(f"Failed to save checkpoint: {e}") from e

    async def load_checkpoint(self, file_path: str) -> CheckpointData | None:
        """Load checkpoint for file if exists."""

        file_hash = await self._calculate_file_hash(file_path)
        checkpoint_id = self._generate_checkpoint_id(file_path, file_hash)
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path) as f:
                data = json.load(f)

            checkpoint = CheckpointData.model_validate(data)

            # Validate integrity
            if not self._validate_checkpoint_integrity(checkpoint):
                logger.warning(f"Corrupted checkpoint detected: {checkpoint_id}")
                await self._remove_checkpoint(checkpoint_id)
                return None

            # Check file hasn't changed
            if checkpoint.file_hash != file_hash:
                logger.info(f"File changed since checkpoint: {file_path}")
                await self._remove_checkpoint(checkpoint_id)
                return None

            logger.info(f"Checkpoint loaded: {checkpoint_id} at stage {checkpoint.stage}")
            return checkpoint

        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    async def has_checkpoint(self, file_path: str) -> bool:
        """Check if valid checkpoint exists for file."""
        checkpoint = await self.load_checkpoint(file_path)
        return checkpoint is not None

    async def remove_checkpoint(self, file_path: str) -> bool:
        """Remove checkpoint for file."""
        file_hash = await self._calculate_file_hash(file_path)
        checkpoint_id = self._generate_checkpoint_id(file_path, file_hash)
        return await self._remove_checkpoint(checkpoint_id)

    async def cleanup_old_checkpoints(self, max_age_days: int = 7) -> int:
        """Clean up old checkpoint files."""

        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)
        removed_count = 0

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)

                created_at = datetime.fromisoformat(data["created_at"])
                if created_at < cutoff_date:
                    checkpoint_file.unlink()
                    removed_count += 1
                    logger.debug(f"Cleaned up old checkpoint: {checkpoint_file.name}")

            except Exception as e:
                logger.warning(f"Error cleaning checkpoint {checkpoint_file}: {e}")

        return removed_count

class RecoveryService:
    """Handle processing recovery from checkpoints."""

    def __init__(
        self,
        checkpoint_manager: CheckpointManager,
        expense_processor: ExpenseProcessor
    ):
        self.checkpoint_manager = checkpoint_manager
        self.expense_processor = expense_processor

    async def resume_processing(
        self,
        file_path: str,
        force_fresh: bool = False
    ) -> ProcessingResult:
        """Resume processing from checkpoint or start fresh."""

        if force_fresh:
            await self.checkpoint_manager.remove_checkpoint(file_path)
            return await self.expense_processor.process_receipt_file(file_path)

        checkpoint = await self.checkpoint_manager.load_checkpoint(file_path)

        if not checkpoint:
            logger.info(f"No checkpoint found for {file_path}, processing fresh")
            return await self.expense_processor.process_receipt_file(file_path)

        logger.info(f"Resuming processing from stage: {checkpoint.stage}")

        # Resume from appropriate stage
        if checkpoint.stage == ProcessingStage.GEMINI_EXTRACTED:
            return await self._resume_from_gemini_extraction(checkpoint)
        elif checkpoint.stage == ProcessingStage.RULES_APPLIED:
            return await self._resume_from_business_rules(checkpoint)
        elif checkpoint.stage == ProcessingStage.TAX_CALCULATED:
            return await self._resume_from_tax_calculation(checkpoint)
        else:
            logger.warning(f"Unknown checkpoint stage: {checkpoint.stage}")
            return await self.expense_processor.process_receipt_file(checkpoint.file_path)

    async def _resume_from_gemini_extraction(
        self,
        checkpoint: CheckpointData
    ) -> ProcessingResult:
        """Resume processing after Gemini extraction."""

        logger.info("Resuming from Gemini extraction checkpoint")

        # Reconstruct extracted receipt from checkpoint
        extracted_receipt = ExtractedReceipt.model_validate(
            checkpoint.data["extracted_receipt"]
        )

        # Continue with business rules and beyond
        return await self.expense_processor.process_from_extracted_receipt(
            extracted_receipt,
            checkpoint.file_path,
            checkpoint.correlation_id
        )

class ProcessingStage(str, Enum):
    """Processing stages for checkpoints."""
    GEMINI_EXTRACTED = "gemini_extracted"
    RULES_APPLIED = "rules_applied"
    TAX_CALCULATED = "tax_calculated"
    QB_READY = "qb_ready"

class CheckpointData(BaseModel):
    """Checkpoint data structure."""
    checkpoint_id: str
    file_path: str
    file_hash: str
    stage: ProcessingStage
    data: dict[str, Any]
    correlation_id: str | None = None
    created_at: datetime
    system_version: str
    checksum: str
```

### CLI Integration
```bash
# Automatic recovery (default behavior)
quickexpense upload receipt.pdf
# Output: "Resuming from checkpoint (Gemini extraction completed)"

# Force fresh processing
quickexpense upload receipt.pdf --fresh
# Output: "Processing fresh (ignoring existing checkpoint)"

# Resume specific file
quickexpense resume receipt.pdf

# Checkpoint management
quickexpense checkpoint list
quickexpense checkpoint clean --older-than 7
quickexpense checkpoint remove receipt.pdf
```

### Enhanced Error Handling
```python
class ProcessingWithCheckpoints:
    """Enhanced processor with checkpoint integration."""

    async def process_with_recovery(
        self,
        file_path: str,
        business_context: dict | None = None,
        force_fresh: bool = False
    ) -> ProcessingResult:
        """Process with automatic checkpointing."""

        correlation_id = self._generate_correlation_id()

        try:
            # Check for existing checkpoint
            if not force_fresh:
                result = await self.recovery_service.resume_processing(file_path)
                if result:
                    return result

            # Stage 1: Gemini Extraction (expensive)
            logger.info("Starting Gemini extraction...")
            extracted_receipt = await self.gemini_service.extract_receipt_data(file_path)

            # Checkpoint after expensive operation
            await self.checkpoint_manager.save_checkpoint(
                file_path=file_path,
                stage=ProcessingStage.GEMINI_EXTRACTED,
                data={"extracted_receipt": extracted_receipt.model_dump()},
                correlation_id=correlation_id
            )

            # Stage 2: Business Rules (computed state)
            logger.info("Applying business rules...")
            categorized_items = await self.business_rules_engine.categorize_items(
                extracted_receipt.line_items
            )

            # Checkpoint business rules
            await self.checkpoint_manager.save_checkpoint(
                file_path=file_path,
                stage=ProcessingStage.RULES_APPLIED,
                data={
                    "extracted_receipt": extracted_receipt.model_dump(),
                    "categorized_items": [item.model_dump() for item in categorized_items]
                },
                correlation_id=correlation_id
            )

            # Stage 3: QuickBooks submission (fast, idempotent)
            logger.info("Creating QuickBooks entries...")
            qb_result = await self.quickbooks_service.create_expense(categorized_items)

            # Clean up checkpoint after successful completion
            await self.checkpoint_manager.remove_checkpoint(file_path)

            return ProcessingResult(
                success=True,
                extracted_receipt=extracted_receipt,
                categorized_items=categorized_items,
                qb_result=qb_result,
                resumed_from_checkpoint=False
            )

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            # Checkpoint is preserved for retry
            raise
```

## Testing Requirements

### Unit Tests
- [ ] Test checkpoint creation and atomic writes
- [ ] Test checkpoint loading and validation
- [ ] Test recovery from various processing stages
- [ ] Test checkpoint cleanup and lifecycle management
- [ ] Test error handling and corruption recovery

### Integration Tests
- [ ] Test end-to-end recovery scenarios
- [ ] Test batch processing with checkpoints
- [ ] Test system restart recovery
- [ ] Test concurrent checkpoint operations
- [ ] Test checkpoint compatibility across versions

### Recovery Test Scenarios
```python
# Recovery Test Cases
RECOVERY_TEST_SCENARIOS = {
    "gemini_extraction_failure": {
        "description": "Fail after Gemini extraction, resume from checkpoint",
        "failure_point": "after_gemini",
        "expected_behavior": "resume_from_business_rules"
    },
    "network_interruption": {
        "description": "Network failure during QuickBooks submission",
        "failure_point": "during_qb_submission",
        "expected_behavior": "retry_qb_submission"
    },
    "corrupted_checkpoint": {
        "description": "Corrupted checkpoint file detected",
        "corruption_type": "invalid_json",
        "expected_behavior": "process_fresh"
    }
}
```

## Dependencies
- Existing expense processor ✅ Completed
- Audit logging system (PRE-117) - Concurrent development
- Batch processing system (PRE-118) - Concurrent development

## Definition of Done
- [ ] Checkpoint creation after expensive operations
- [ ] Automatic recovery detection and resume capability
- [ ] Checkpoint lifecycle management with cleanup
- [ ] CLI integration with resume and fresh options
- [ ] Batch processing checkpoint support
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate recovery scenarios
- [ ] Error handling covers corruption and edge cases
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)

## Validation Scenarios

### Scenario 1: Network Interruption Recovery
**Given** processing receipt with unstable internet connection
**When** network fails after Gemini extraction but before QB submission
**Then**
- Gemini extraction results saved to checkpoint
- User can resume processing later with `quickexpense upload receipt.pdf`
- Processing resumes from business rules stage
- No duplicate Gemini API calls or charges
- Complete audit trail maintained across interruption

### Scenario 2: Batch Processing Recovery
**Given** batch processing 50 receipts with system crash at file 30
**When** restarting batch processing
**Then**
- Files 1-29 skipped (already processed)
- File 30 resumes from last checkpoint
- Files 31-50 processed normally
- No duplicate QuickBooks entries created
- Batch summary reflects recovered processing

### Scenario 3: Checkpoint Cleanup and Maintenance
**Given** 100 old checkpoint files from previous processing
**When** running automatic cleanup
**Then**
- Checkpoints older than 7 days removed automatically
- Active checkpoints preserved
- Disk space reclaimed efficiently
- No impact on current processing operations

## Risk Mitigation
- **Disk Space:** Automatic cleanup with configurable retention
- **Checkpoint Corruption:** Integrity validation and atomic writes
- **Version Compatibility:** Version checks and graceful degradation
- **Performance Impact:** Minimal overhead with async I/O

## Success Metrics
- Zero data loss during processing interruptions
- <100ms checkpoint creation overhead
- 99% successful recovery from valid checkpoints
- Automatic cleanup prevents disk space issues
- User satisfaction with transparent recovery experience
