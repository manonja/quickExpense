"""Tests for audit logging service."""

import json
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from quickexpense.core.logging_config import LoggingConfig, StructuredFormatter
from quickexpense.services.audit_logger import AuditLogger, CorrelationIDGenerator


class TestCorrelationIDGenerator:
    """Test correlation ID generation."""

    def test_generates_unique_ids(self):
        """Test that generated IDs are unique."""
        generator = CorrelationIDGenerator()

        id1 = generator.generate()
        time.sleep(0.001)  # Ensure different timestamp
        id2 = generator.generate()

        assert id1 != id2
        assert id1.startswith("req_")
        assert id2.startswith("req_")
        assert (
            len(id1) == 27
        )  # req_ + 8 chars (date) + _ + 6 chars (time) + 8 chars (uuid)

    def test_id_format(self):
        """Test correlation ID format."""
        generator = CorrelationIDGenerator()
        correlation_id = generator.generate()

        parts = correlation_id.split("_")
        assert len(parts) == 3
        assert parts[0] == "req"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 14  # HHMMSS + 8 char uuid


class TestStructuredFormatter:
    """Test JSON structured logging formatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = StructuredFormatter(sanitize_sensitive=True)

    def test_basic_log_formatting(self):
        """Test basic log record formatting."""
        import logging

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "path"
        assert log_data["function"] == "<unknown>"
        assert log_data["line"] == 42
        assert "timestamp" in log_data

    def test_extra_fields_inclusion(self):
        """Test that extra fields are included in logs."""
        import logging

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.correlation_id = "test_123"
        record.event_type = "test_event"
        record.entity_type = "sole_proprietorship"

        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["correlation_id"] == "test_123"
        assert log_data["event_type"] == "test_event"
        assert log_data["entity_type"] == "sole_proprietorship"
        assert log_data["tax_form"] == "T2125"

    def test_sensitive_data_sanitization(self):
        """Test that sensitive data is properly sanitized."""
        import logging

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add sensitive data
        record.access_token = "secret_token_123"
        record.api_key = "api_key_456"
        record.user_data = {"password": "secret123", "name": "John"}

        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["access_token"] == "***REDACTED***"
        assert log_data["api_key"] == "***REDACTED***"
        assert log_data["user_data"]["password"] == "***REDACTED***"
        assert log_data["user_data"]["name"] == "John"

    def test_exception_formatting(self):
        """Test exception formatting in logs."""
        import logging
        import sys

        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/test/path.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            formatted = self.formatter.format(record)
            log_data = json.loads(formatted)

            assert log_data["level"] == "ERROR"
            assert log_data["message"] == "Error occurred"
            assert "exception" in log_data
            assert "ValueError: Test exception" in log_data["exception"]


class TestAuditLogger:
    """Test audit logging functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use temporary directory for test logs
        self.temp_dir = tempfile.mkdtemp()
        self.config = LoggingConfig(
            audit_log_path=Path(self.temp_dir) / "audit",
            performance_log_path=Path(self.temp_dir) / "performance",
            enable_console_output=False,  # Disable for tests
        )
        self.audit_logger = AuditLogger(self.config)

    def test_start_expense_processing(self):
        """Test expense processing start logging."""
        test_file = "/path/to/receipt.jpg"
        user_context = {"entity_type": "sole_proprietorship", "verbose": True}

        correlation_id = self.audit_logger.start_expense_processing(
            test_file, user_context
        )

        assert correlation_id.startswith("req_")
        assert len(correlation_id) == 27

        # Check log file was created
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        assert log_file.exists()

        # Check log content
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "expense_processing_start"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["file_path"] == test_file
            assert log_data["entity_type"] == "sole_proprietorship"
            assert "system_info" in log_data

    def test_log_gemini_extraction(self):
        """Test Gemini extraction logging."""
        correlation_id = "test_123"
        processing_time = 2.5
        confidence_score = 0.95
        extracted_data = {
            "vendor_name": "Test Vendor",
            "total_amount": Decimal("100.00"),
            "currency": "CAD",
            "line_items": [{"description": "Item 1"}, {"description": "Item 2"}],
        }

        self.audit_logger.log_gemini_extraction(
            correlation_id, processing_time, confidence_score, extracted_data
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "gemini_extraction"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["processing_time_seconds"] == 2.5
            assert log_data["confidence_score"] == 0.95
            assert log_data["success"] is True
            assert log_data["extraction_results"]["vendor_name"] == "Test Vendor"
            assert log_data["extraction_results"]["line_item_count"] == 2

    def test_log_gemini_extraction_with_error(self):
        """Test Gemini extraction logging with error."""
        correlation_id = "test_123"
        processing_time = 1.0
        confidence_score = 0.0
        extracted_data: dict[str, Any] = {}
        error = "API rate limit exceeded"

        self.audit_logger.log_gemini_extraction(
            correlation_id,
            processing_time,
            confidence_score,
            extracted_data,
            error=error,
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "gemini_extraction"
            assert log_data["success"] is False
            assert log_data["error"] == error
            assert log_data["level"] == "ERROR"

    def test_log_business_rules_application(self):
        """Test business rules application logging."""
        correlation_id = "test_123"
        rules_applied = [
            {
                "id": "rule_1",
                "name": "Hotel Accommodation",
                "confidence": 0.95,
                "items_affected": 1,
                "category": "Travel-Lodging",
                "t2125_line_item": "8890",
                "deductibility_percentage": 100,
                "ita_reference": None,
            }
        ]
        categorized_items = [
            {
                "category": "Travel-Lodging",
                "amount": Decimal("200.00"),
                "deductible_amount": Decimal("200.00"),
                "t2125_line_item": "8890",
                "compliance_note": None,
            }
        ]

        self.audit_logger.log_business_rules_application(
            correlation_id, rules_applied, categorized_items
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "business_rules_application"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["rules_summary"]["rules_applied_count"] == 1
            assert log_data["rules_summary"]["average_confidence"] == 0.95
            assert log_data["categorization_summary"]["total_items"] == 1
            assert log_data["categorization_summary"]["deductibility_rate"] == 100.0

    def test_log_quickbooks_integration_success(self):
        """Test successful QuickBooks integration logging."""
        correlation_id = "test_123"
        qb_entries = [
            {
                "id": "191",
                "amount": 200.0,
                "account": "Travel - Lodging",
                "vendor": "Test Hotel",
            }
        ]
        processing_time = 1.2

        self.audit_logger.log_quickbooks_integration(
            correlation_id, qb_entries, processing_time
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "quickbooks_integration"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["success"] is True
            assert log_data["integration_results"]["entries_created"] == 1
            assert log_data["integration_results"]["qb_entry_ids"] == ["191"]
            assert log_data["level"] == "INFO"

    def test_log_quickbooks_integration_failure(self):
        """Test failed QuickBooks integration logging."""
        correlation_id = "test_123"
        qb_entries: list[dict[str, Any]] = []
        processing_time = 0.5
        errors = ["Authentication failed", "Invalid company ID"]

        self.audit_logger.log_quickbooks_integration(
            correlation_id, qb_entries, processing_time, errors
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "quickbooks_integration"
            assert log_data["success"] is False
            assert log_data["errors"] == errors
            assert log_data["error_count"] == 2
            assert log_data["level"] == "ERROR"

    def test_complete_expense_processing(self):
        """Test expense processing completion logging."""
        correlation_id = "test_123"
        total_processing_time = 8.5
        final_status = "success"
        summary = {
            "vendor": "Test Vendor",
            "total_amount": Decimal("150.00"),
            "categories_count": 2,
            "rules_applied": 3,
            "qb_entries_created": 1,
            "deductible_amount": Decimal("125.00"),
            "entity_type": "sole_proprietorship",
            "tax_form": "T2125",
            "compliance_notes": ["CRA Section 67.1 applies"],
        }

        self.audit_logger.complete_expense_processing(
            correlation_id, total_processing_time, final_status, summary
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "expense_processing_complete"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["total_processing_time_seconds"] == 8.5
            assert log_data["final_status"] == "success"
            assert log_data["processing_summary"]["vendor"] == "Test Vendor"
            assert log_data["processing_summary"]["tax_form"] == "T2125"
            assert log_data["level"] == "INFO"

    def test_log_error(self):
        """Test error logging."""
        correlation_id = "test_123"
        error_type = "QuickBooksAuthenticationError"
        error_message = "Access token expired"
        context = {"api_endpoint": "/v3/company/123/purchase"}
        recovery_action = "Refresh OAuth token"

        self.audit_logger.log_error(
            correlation_id, error_type, error_message, context, recovery_action
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "error_occurred"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["error_type"] == error_type
            assert log_data["error_message"] == error_message
            assert log_data["context"] == context
            assert log_data["recovery_action"] == recovery_action
            assert log_data["level"] == "ERROR"

    def test_get_audit_summary(self):
        """Test audit summary generation."""
        correlation_id = "test_123"

        summary = self.audit_logger.get_audit_summary(correlation_id)

        assert summary["correlation_id"] == correlation_id
        assert "audit_log_location" in summary
        assert summary["retention_policy"] == "7 years (CRA compliance)"
        assert summary["log_format"] == "JSON structured"

    def test_performance_metric_logging(self):
        """Test performance metric logging."""
        correlation_id = "test_123"
        operation = "gemini_api_call"
        duration = 2.5
        metadata = {"model": "gemini-2.0-flash", "tokens": 150}

        self.audit_logger.log_performance_metric(
            correlation_id, operation, duration, success=True, metadata=metadata
        )

        # Check log content
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)

            assert log_data["event_type"] == "performance_metric"
            assert log_data["correlation_id"] == correlation_id
            assert log_data["operation"] == operation
            assert log_data["duration_seconds"] == 2.5
            assert log_data["success"] is True
            assert log_data["metadata"] == metadata


class TestLoggingConfig:
    """Test logging configuration."""

    def test_default_configuration(self):
        """Test default logging configuration values."""
        config = LoggingConfig()

        assert config.log_level == "INFO"
        assert config.log_format == "json"
        assert config.max_file_size_mb == 10
        assert config.backup_count == 365
        assert config.retention_years == 7
        assert config.enable_console_output is True
        assert config.sanitize_sensitive_data is True

    def test_custom_configuration(self):
        """Test custom logging configuration."""
        config = LoggingConfig(
            log_level="DEBUG",
            max_file_size_mb=5,
            backup_count=100,
            retention_years=3,
        )

        assert config.log_level == "DEBUG"
        assert config.max_file_size_mb == 5
        assert config.backup_count == 100
        assert config.retention_years == 3

    def test_setup_directories(self):
        """Test directory creation."""
        temp_dir = tempfile.mkdtemp()
        config = LoggingConfig(
            audit_log_path=Path(temp_dir) / "test_audit",
            performance_log_path=Path(temp_dir) / "test_performance",
        )

        config.setup_directories()

        assert config.audit_log_path.exists()
        assert config.performance_log_path.exists()
        assert config.audit_log_path.is_dir()
        assert config.performance_log_path.is_dir()


class TestAuditTrailIntegration:
    """Integration tests for complete audit trail."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = LoggingConfig(
            audit_log_path=Path(self.temp_dir) / "audit",
            enable_console_output=False,
        )
        self.audit_logger = AuditLogger(self.config)

    def test_complete_audit_trail(self):
        """Test complete audit trail from start to finish."""
        # Start processing
        correlation_id = self.audit_logger.start_expense_processing(
            "/path/to/receipt.jpg", {"entity_type": "sole_proprietorship"}
        )

        # Log Gemini extraction
        self.audit_logger.log_gemini_extraction(
            correlation_id, 2.5, 0.95, {"vendor_name": "Test Vendor", "line_items": []}
        )

        # Log business rules
        self.audit_logger.log_business_rules_application(
            correlation_id, [{"id": "rule1", "confidence": 0.9}], []
        )

        # Log QuickBooks integration
        self.audit_logger.log_quickbooks_integration(
            correlation_id, [{"id": "191", "amount": 100.0}], 1.0
        )

        # Complete processing
        self.audit_logger.complete_expense_processing(
            correlation_id, 5.0, "success", {"vendor": "Test Vendor"}
        )

        # Verify all events are logged
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            lines = f.readlines()

        assert len(lines) == 5  # Five log events

        events = [json.loads(line)["event_type"] for line in lines]
        expected_events = [
            "expense_processing_start",
            "gemini_extraction",
            "business_rules_application",
            "quickbooks_integration",
            "expense_processing_complete",
        ]

        assert events == expected_events

        # Verify all events have the same correlation ID
        correlation_ids = [json.loads(line)["correlation_id"] for line in lines]
        assert all(cid == correlation_id for cid in correlation_ids)

    def test_error_audit_trail(self):
        """Test audit trail with error conditions."""
        correlation_id = self.audit_logger.start_expense_processing(
            "/path/to/receipt.jpg", {"entity_type": "sole_proprietorship"}
        )

        # Log failed Gemini extraction
        self.audit_logger.log_gemini_extraction(
            correlation_id, 1.0, 0.0, {}, error="API rate limit exceeded"
        )

        # Log error
        self.audit_logger.log_error(
            correlation_id, "GeminiAPIError", "Rate limit exceeded", {"retry_after": 60}
        )

        # Complete with failure status
        self.audit_logger.complete_expense_processing(
            correlation_id, 2.0, "failed", {"error": "Gemini extraction failed"}
        )

        # Verify error logging
        log_file = self.config.audit_log_path / "quickexpense_audit.log"
        with log_file.open() as f:
            lines = f.readlines()

        # Check that errors are logged at ERROR level
        error_logs = [
            json.loads(line) for line in lines if json.loads(line)["level"] == "ERROR"
        ]
        assert len(error_logs) >= 2  # Failed extraction and explicit error
