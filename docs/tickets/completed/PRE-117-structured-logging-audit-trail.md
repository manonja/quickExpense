# PRE-117: Enhanced Structured Logging with Audit Trail

**Type:** Enhancement
**Priority:** High (Professional/Audit Requirements)
**Effort:** 2 Story Points
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** sole proprietor subject to CRA audits
**I want** detailed, structured logs of all expense processing activities
**So that** I can provide complete audit trails and troubleshoot any QuickBooks integration issues

## Business Value
- **Problem:** Current logging lacks structure and audit trail requirements for professional use
- **Impact:** Difficult CRA audit defense, challenging troubleshooting, unprofessional appearance
- **Solution:** Comprehensive structured logging with correlation IDs and audit compliance

## Description
Implement a professional-grade logging system with JSON structured output, correlation tracking, performance monitoring, and audit trail capabilities. The system should meet CRA requirements for business record keeping while providing detailed debugging information.

## Audit Requirements (CRA Guidelines)
**Business Record Keeping Requirements:**
- Complete transaction trails
- Processing timestamps and duration
- Decision rationale (business rules applied)
- System confidence levels
- Integration results (QuickBooks entry IDs)
- Error conditions and resolutions
- 7-year retention requirement

## Acceptance Criteria

### AC1: Structured JSON Logging
- [ ] Implement JSON-formatted log output
- [ ] Include correlation IDs for request tracking
- [ ] Add structured fields for key business data
- [ ] Support multiple log levels (DEBUG, INFO, WARN, ERROR)
- [ ] Ensure consistent timestamp formatting (ISO 8601 UTC)

### AC2: Audit Trail Components
- [ ] Log complete expense processing pipeline
- [ ] Track business rule application and confidence
- [ ] Record QuickBooks integration results
- [ ] Capture Gemini AI processing metadata
- [ ] Include provincial tax calculations and decisions
- [ ] Store processing performance metrics

### AC3: Log Management
- [ ] Implement rotating file handlers (10MB max per file)
- [ ] Maintain 7-year retention policy for audit compliance
- [ ] Create log cleanup utilities
- [ ] Support log export for CRA submission
- [ ] Handle log file corruption gracefully

### AC4: Performance Monitoring
- [ ] Time each processing stage
- [ ] Track API call durations (Gemini, QuickBooks)
- [ ] Monitor system resource usage
- [ ] Alert on processing anomalies
- [ ] Generate performance reports

### AC5: Enhanced CLI Integration
- [ ] Add correlation IDs to CLI output
- [ ] Support verbose logging mode
- [ ] Include audit trail summary in results
- [ ] Provide log file location in output
- [ ] Support audit log export commands

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/services/audit_logger.py` - New audit logging service
- `src/quickexpense/core/logging_config.py` - Logging configuration
- `src/quickexpense/cli.py` - Enhanced CLI with audit integration
- `src/quickexpense/services/` - Add audit logging to all services
- `tests/services/test_audit_logger.py` - Comprehensive tests

### AuditLogger Service
```python
class AuditLogger:
    """Professional audit logging for CRA compliance."""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.logger = self._setup_structured_logger()
        self.correlation_id_generator = CorrelationIDGenerator()

    def start_expense_processing(
        self,
        file_path: str,
        user_context: dict
    ) -> str:
        """Start processing audit trail."""
        correlation_id = self.correlation_id_generator.generate()

        audit_record = {
            "event_type": "expense_processing_start",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "user_context": user_context,
            "system_version": get_system_version()
        }

        self.logger.info("Expense processing started", extra=audit_record)
        return correlation_id

    def log_gemini_extraction(
        self,
        correlation_id: str,
        processing_time: float,
        confidence_score: float,
        extracted_data: dict,
        api_cost: float | None = None
    ):
        """Log Gemini AI extraction details."""

        audit_record = {
            "event_type": "gemini_extraction",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "processing_time_seconds": processing_time,
            "confidence_score": confidence_score,
            "extracted_fields": list(extracted_data.keys()),
            "api_cost_usd": api_cost,
            "vendor_name": extracted_data.get("vendor_name"),
            "total_amount": str(extracted_data.get("total_amount", "0")),
            "line_item_count": len(extracted_data.get("line_items", []))
        }

        self.logger.info("Gemini extraction completed", extra=audit_record)

    def log_business_rules_application(
        self,
        correlation_id: str,
        rules_applied: list[dict],
        categorized_items: list[dict],
        provincial_context: dict | None = None
    ):
        """Log business rules and categorization decisions."""

        audit_record = {
            "event_type": "business_rules_application",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "rules_applied_count": len(rules_applied),
            "rules_applied": [
                {
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "confidence": rule["confidence"],
                    "items_affected": rule["items_affected"],
                    "t2125_line_item": rule.get("t2125_line_item"),  # Entity-aware form mapping
                    "deductibility_percentage": rule.get("deductibility_percentage")
                }
                for rule in rules_applied
            ],
            "categorization_summary": {
                "total_items": len(categorized_items),
                "categories": list(set(item["category"] for item in categorized_items)),
                "total_deductible": sum(item.get("deductible_amount", 0) for item in categorized_items),
                "t2125_line_items": list(set(item.get("t2125_line_item") for item in categorized_items if item.get("t2125_line_item")))
            },
            "provincial_context": provincial_context,
            "entity_type": user_context.get("entity_type", "sole_proprietorship"),
            "tax_form": {
                "sole_proprietorship": "T2125",
                "corporation": "T2",
                "partnership": "T5013"
            }.get(user_context.get("entity_type", "sole_proprietorship"), "T2125")
        }

        self.logger.info("Business rules applied", extra=audit_record)

    def log_quickbooks_integration(
        self,
        correlation_id: str,
        qb_entries: list[dict],
        processing_time: float,
        errors: list[str] | None = None
    ):
        """Log QuickBooks integration results."""

        audit_record = {
            "event_type": "quickbooks_integration",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "processing_time_seconds": processing_time,
            "entries_created": len(qb_entries),
            "qb_entry_ids": [entry["id"] for entry in qb_entries],
            "total_amount_submitted": sum(entry["amount"] for entry in qb_entries),
            "accounts_used": list(set(entry["account"] for entry in qb_entries)),
            "success": len(errors) == 0 if errors else True,
            "errors": errors or []
        }

        if errors:
            self.logger.error("QuickBooks integration failed", extra=audit_record)
        else:
            self.logger.info("QuickBooks integration completed", extra=audit_record)

    def complete_expense_processing(
        self,
        correlation_id: str,
        total_processing_time: float,
        final_status: str,
        summary: dict
    ):
        """Complete processing audit trail."""

        audit_record = {
            "event_type": "expense_processing_complete",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "total_processing_time_seconds": total_processing_time,
            "final_status": final_status,
            "processing_summary": summary,
            "compliance_notes": summary.get("compliance_notes", [])
        }

        self.logger.info("Expense processing completed", extra=audit_record)
```

### Logging Configuration
```python
class LoggingConfig(BaseModel):
    """Audit logging configuration."""

    log_level: str = "INFO"
    log_format: str = "json"
    max_file_size_mb: int = 10
    backup_count: int = 365  # ~1 year of daily logs
    retention_years: int = 7
    audit_log_path: Path = Path("logs/audit")
    performance_log_path: Path = Path("logs/performance")

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""

        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add extra fields from audit records
        if hasattr(record, "correlation_id"):
            log_entry.update({
                key: getattr(record, key)
                for key in record.__dict__
                if key not in {"name", "msg", "args", "levelname", "levelno",
                             "pathname", "filename", "module", "lineno", "funcName",
                             "created", "msecs", "relativeCreated", "thread",
                             "threadName", "processName", "process", "stack_info",
                             "exc_info", "exc_text", "message"}
            })

            # Add entity-aware tax form information
            if hasattr(record, "entity_type"):
                log_entry["tax_form"] = {
                    "sole_proprietorship": "T2125",
                    "corporation": "T2",
                    "partnership": "T5013"
                }.get(getattr(record, "entity_type"), "unknown")

        return json.dumps(log_entry, default=str, ensure_ascii=False)
```

## Testing Requirements

### Unit Tests
- [ ] Test JSON log formatting
- [ ] Test correlation ID generation and tracking
- [ ] Test log rotation and cleanup
- [ ] Test audit trail completeness
- [ ] Test performance monitoring

### Integration Tests
- [ ] Test end-to-end audit trail with real receipt
- [ ] Test log file management under load
- [ ] Test audit log export functionality
- [ ] Test integration with all services
- [ ] Test compliance with CRA requirements

### Test Scenarios
```python
# Audit Trail Test Cases
AUDIT_TEST_SCENARIOS = {
    "complete_processing": {
        "description": "Full receipt processing audit trail",
        "steps": [
            "start_processing",
            "gemini_extraction",
            "business_rules",
            "quickbooks_integration",
            "complete_processing"
        ],
        "expected_fields": [
            "correlation_id", "timestamp", "event_type",
            "processing_time", "confidence_scores", "qb_entry_ids"
        ]
    },
    "error_handling": {
        "description": "Error condition audit trail",
        "error_type": "quickbooks_authentication_failure",
        "expected_logs": ["error_logged", "recovery_attempted", "final_status"]
    }
}
```

## CLI Integration

### Enhanced Command Output
```bash
# Existing functionality with audit integration
$ quickexpense upload receipt.pdf --verbose

Correlation ID: req_20250919_142355_a8b9c
Processing receipt: receipt.pdf
Audit trail: logs/audit/20250919.log

[Processing stages with audit logging...]

=== Audit Summary ===
Correlation ID: req_20250919_142355_a8b9c
Processing Time: 8.45 seconds
Gemini Confidence: 96.2%
Rules Applied: 3
QuickBooks Entries: 2 (IDs: 191, 192)
Audit Log: logs/audit/20250919.log
```

### New Audit Commands
```bash
# Export audit logs for CRA
quickexpense audit export --start-date 2025-01-01 --end-date 2025-12-31 --format csv

# Search audit trail
quickexpense audit search --correlation-id req_20250919_142355_a8b9c

# Performance report
quickexpense audit performance --last-30-days
```

## Dependencies
- Existing CLI interface ✅ Completed
- Business rules engine (PRE-107) ✅ Completed
- QuickBooks integration (PRE-110) ✅ Completed

## Definition of Done
- [ ] JSON structured logging implemented across all services
- [ ] Complete audit trail for expense processing pipeline
- [ ] Log rotation and 7-year retention policy
- [ ] Performance monitoring and reporting
- [ ] Enhanced CLI with audit integration
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate audit completeness
- [ ] CRA compliance requirements met
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)

## Validation Scenarios

### Scenario 1: CRA Audit Preparation (T2125 Focus)
**Given** sole proprietor preparing for CRA audit
**When** exporting audit logs for tax year 2025
**Then**
- Complete transaction trails available for all processed receipts
- Entity type "sole_proprietorship" and T2125 form logged consistently
- T2125 line item mappings documented for each expense
- Correlation IDs link all related log entries
- Business rule decisions documented with confidence scores
- Deductibility percentages (meals 50%, office supplies 100%) logged
- QuickBooks entry IDs traceable to original receipts
- Provincial tax calculations preserved
- Export format suitable for CRA submission with T2125 line references

### Scenario 2: System Troubleshooting
**Given** QuickBooks integration failure
**When** investigating using correlation ID
**Then**
- Complete processing timeline visible in logs
- Error conditions and retry attempts logged
- Performance bottlenecks identified
- Recovery actions documented
- Root cause analysis possible from audit trail

### Scenario 3: Performance Monitoring
**Given** batch processing of 50 receipts
**When** reviewing performance logs
**Then**
- Processing time per receipt tracked
- API call performance monitored
- Resource usage patterns identified
- Bottlenecks and optimization opportunities visible
- Performance trends over time available

## Risk Mitigation
- **Log Volume:** Configurable log levels and rotation
- **Performance Impact:** Minimal overhead with async logging
- **Storage Requirements:** Automatic cleanup with retention policy
- **Privacy Concerns:** Sanitize sensitive data in logs

## Success Metrics
- 100% audit trail coverage for all processing steps
- <5ms logging overhead per transaction
- Zero data loss in audit logs
- CRA audit readiness achieved
- Troubleshooting time reduced by >50%
