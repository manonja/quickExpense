"""Professional audit logging service for CRA compliance."""

import platform
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from quickexpense import __version__
from quickexpense.core.logging_config import LoggingConfig, setup_audit_logging


class CorrelationIDGenerator:
    """Generate unique correlation IDs for tracking audit trails."""

    def __init__(self) -> None:
        """Initialize the correlation ID generator."""
        self.session_id = uuid.uuid4().hex[:8]

    def generate(self) -> str:
        """Generate a unique correlation ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        time_part = datetime.now(UTC).strftime("%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"req_{timestamp}_{time_part}{unique_id}"


class AuditLogger:
    """Professional audit logging for CRA compliance and troubleshooting."""

    def __init__(self, config: LoggingConfig | None = None) -> None:
        """Initialize audit logger with configuration."""
        self.config = config or LoggingConfig()
        self.logger = setup_audit_logging(self.config)
        self.correlation_id_generator = CorrelationIDGenerator()

    def start_expense_processing(
        self, file_path: str, user_context: dict[str, Any] | None = None
    ) -> str:
        """Start processing audit trail with correlation ID."""
        correlation_id = self.correlation_id_generator.generate()
        user_context = user_context or {}

        try:
            path_obj = Path(file_path)
            file_size = path_obj.stat().st_size if path_obj.exists() else 0
        except OSError:
            file_size = 0

        audit_record = {
            "event_type": "expense_processing_start",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "file_path": str(file_path),
            "file_name": Path(file_path).name,
            "file_size_bytes": file_size,
            "user_context": user_context,
            "system_info": {
                "version": __version__,
                "platform": platform.platform(),
                "python_version": platform.python_version(),
            },
            "entity_type": user_context.get("entity_type", "sole_proprietorship"),
        }

        self.logger.info("Expense processing started", extra=audit_record)
        return correlation_id

    def log_gemini_extraction(  # noqa: PLR0913
        self,
        correlation_id: str,
        processing_time: float,
        confidence_score: float,
        extracted_data: Any,  # Support both dict and Pydantic models  # noqa: ANN401
        api_cost: float | None = None,
        error: str | None = None,
    ) -> None:
        """Log Gemini AI extraction details and performance."""
        # Handle both dict and Pydantic model formats for backward compatibility
        if hasattr(extracted_data, "line_items"):
            # Pydantic model (ExtractedReceipt)
            line_items = extracted_data.line_items
            vendor_name = extracted_data.vendor_name
            total_amount = str(extracted_data.total_amount)
            currency = extracted_data.currency
            date = str(extracted_data.transaction_date)
            # Get field names from model
            fields_extracted = list(extracted_data.model_fields.keys())
        else:
            # Dictionary format
            line_items = extracted_data.get("line_items", [])
            vendor_name = extracted_data.get("vendor_name")
            total_amount = str(extracted_data.get("total_amount", "0"))
            currency = extracted_data.get("currency", "CAD")
            date = str(extracted_data.get("date", ""))
            fields_extracted = list(extracted_data.keys())

        audit_record = {
            "event_type": "gemini_extraction",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "processing_time_seconds": round(processing_time, 3),
            "confidence_score": round(confidence_score, 3),
            "success": error is None,
            "error": error,
            "extraction_results": {
                "vendor_name": vendor_name,
                "total_amount": total_amount,
                "currency": currency,
                "date": date,
                "line_item_count": len(line_items),
                "fields_extracted": fields_extracted,
            },
            "performance_metrics": {
                "api_cost_usd": api_cost,
                "processing_speed": round(
                    len(line_items) / max(processing_time, 0.001), 2
                ),
                "throughput": "items_per_second",
            },
        }

        if error:
            self.logger.error("Gemini extraction failed", extra=audit_record)
        else:
            self.logger.info("Gemini extraction completed", extra=audit_record)

    def log_business_rules_application(
        self,
        correlation_id: str,
        rules_applied: list[dict[str, Any]],
        categorized_items: list[dict[str, Any]],
        provincial_context: dict[str, Any] | None = None,
        entity_type: str = "sole_proprietorship",
    ) -> None:
        """Log business rules and categorization decisions."""
        total_deductible = sum(
            item.get("deductible_amount", Decimal(0)) for item in categorized_items
        )
        total_amount = sum(item.get("amount", Decimal(0)) for item in categorized_items)

        audit_record = {
            "event_type": "business_rules_application",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "entity_type": entity_type,
            "rules_summary": {
                "rules_applied_count": len(rules_applied),
                "unique_rules": len({rule.get("id", "") for rule in rules_applied}),
                "average_confidence": round(
                    sum(rule.get("confidence", 0) for rule in rules_applied)
                    / max(len(rules_applied), 1),
                    3,
                ),
            },
            "rules_applied": [
                {
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "confidence": round(rule.get("confidence", 0), 3),
                    "items_affected": rule.get("items_affected", 1),
                    "category": rule.get("category"),
                    "t2125_line_item": rule.get("t2125_line_item"),
                    "deductibility_percentage": rule.get("deductibility_percentage"),
                    "ita_reference": rule.get("ita_reference"),
                }
                for rule in rules_applied
            ],
            "categorization_summary": {
                "total_items": len(categorized_items),
                "total_amount": str(total_amount),
                "total_deductible": str(total_deductible),
                "deductibility_rate": round(
                    float(total_deductible / max(total_amount, Decimal("0.01"))) * 100,
                    2,
                ),
                "categories": list(
                    {item.get("category") for item in categorized_items}
                ),
                "t2125_line_items": list(
                    {
                        item.get("t2125_line_item")
                        for item in categorized_items
                        if item.get("t2125_line_item")
                    }
                ),
            },
            "provincial_context": provincial_context,
            "compliance_notes": [
                item.get("compliance_note")
                for item in categorized_items
                if item.get("compliance_note")
            ],
        }

        self.logger.info("Business rules applied", extra=audit_record)

    def log_quickbooks_integration(
        self,
        correlation_id: str,
        qb_entries: list[dict[str, Any]],
        processing_time: float,
        errors: list[str] | None = None,
    ) -> None:
        """Log QuickBooks integration results and performance."""
        success = not errors
        total_amount = sum(
            float(entry.get("amount", 0)) for entry in qb_entries if success
        )

        audit_record = {
            "event_type": "quickbooks_integration",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "processing_time_seconds": round(processing_time, 3),
            "success": success,
            "integration_results": {
                "entries_created": len(qb_entries) if success else 0,
                "qb_entry_ids": [entry.get("id") for entry in qb_entries if success],
                "total_amount_submitted": round(total_amount, 2),
                "accounts_used": list(
                    {entry.get("account") for entry in qb_entries if success}
                ),
                "vendors_used": list(
                    {entry.get("vendor") for entry in qb_entries if success}
                ),
            },
            "errors": errors or [],
            "error_count": len(errors) if errors else 0,
        }

        if errors:
            self.logger.error("QuickBooks integration failed", extra=audit_record)
        else:
            self.logger.info("QuickBooks integration completed", extra=audit_record)

    def log_provincial_tax_calculation(
        self,
        correlation_id: str,
        province_detection: dict[str, Any],
        tax_breakdown: dict[str, Any],
        itc_calculations: dict[str, Any],
    ) -> None:
        """Log provincial tax calculations and Input Tax Credit eligibility."""
        audit_record = {
            "event_type": "provincial_tax_calculation",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "province_detection": {
                "province": province_detection.get("province"),
                "confidence": round(province_detection.get("confidence", 0), 3),
                "detection_method": province_detection.get("detection_method"),
                "postal_code": province_detection.get("postal_code"),
            },
            "tax_breakdown": {
                "total_amount": str(tax_breakdown.get("total_amount", "0")),
                "tax_amount": str(tax_breakdown.get("tax_amount", "0")),
                "tax_type": tax_breakdown.get("tax_type"),
                "gst_amount": str(tax_breakdown.get("gst_amount", "0")),
                "hst_amount": str(tax_breakdown.get("hst_amount", "0")),
                "pst_amount": str(tax_breakdown.get("pst_amount", "0")),
                "qst_amount": str(tax_breakdown.get("qst_amount", "0")),
            },
            "input_tax_credits": {
                "total_itc": str(itc_calculations.get("total_itc", "0")),
                "gst_itc": str(itc_calculations.get("gst_itc", "0")),
                "hst_itc": str(itc_calculations.get("hst_itc", "0")),
                "qst_itc": str(itc_calculations.get("qst_itc", "0")),
                "gst_registered": itc_calculations.get("gst_registered", False),
            },
        }

        self.logger.info("Provincial tax calculated", extra=audit_record)

    def complete_expense_processing(
        self,
        correlation_id: str,
        total_processing_time: float,
        final_status: str,
        summary: dict[str, Any],
    ) -> None:
        """Complete processing audit trail with final summary."""
        audit_record = {
            "event_type": "expense_processing_complete",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "total_processing_time_seconds": round(total_processing_time, 3),
            "final_status": final_status,
            "processing_summary": {
                "vendor": summary.get("vendor"),
                "total_amount": str(summary.get("total_amount", "0")),
                "categories_count": summary.get("categories_count", 0),
                "rules_applied": summary.get("rules_applied", 0),
                "qb_entries_created": summary.get("qb_entries_created", 0),
                "deductible_amount": str(summary.get("deductible_amount", "0")),
                "entity_type": summary.get("entity_type", "sole_proprietorship"),
                "tax_form": summary.get("tax_form", "T2125"),
            },
            "compliance_notes": summary.get("compliance_notes", []),
            "performance_metrics": {
                "throughput": round(
                    summary.get("items_processed", 1)
                    / max(total_processing_time, 0.001),
                    2,
                ),
                "success_rate": summary.get("success_rate", 100.0),
                "average_confidence": summary.get("average_confidence", 0.0),
            },
        }

        if final_status == "success":
            self.logger.info(
                "Expense processing completed successfully", extra=audit_record
            )
        else:
            self.logger.error("Expense processing failed", extra=audit_record)

    def log_performance_metric(
        self,
        correlation_id: str,
        operation: str,
        duration: float,
        *,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log individual performance metrics for monitoring."""
        perf_record = {
            "event_type": "performance_metric",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": operation,
            "duration_seconds": round(duration, 3),
            "success": success,
            "metadata": metadata or {},
        }

        self.logger.info("Performance metric recorded", extra=perf_record)

    def log_error(
        self,
        correlation_id: str,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
        recovery_action: str | None = None,
    ) -> None:
        """Log errors with context for troubleshooting."""
        error_record = {
            "event_type": "error_occurred",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
            "recovery_action": recovery_action,
        }

        self.logger.error("Error occurred during processing", extra=error_record)

    def get_audit_summary(self, correlation_id: str) -> dict[str, Any]:
        """Get audit summary for a specific correlation ID (for CLI display)."""
        # This would typically query log files or a log aggregation system
        # For now, return a basic structure that CLI can use
        return {
            "correlation_id": correlation_id,
            "audit_log_location": str(
                self.config.audit_log_path / "quickexpense_audit.log"
            ),
            "retention_policy": f"{self.config.retention_years} years (CRA compliance)",
            "log_format": "JSON structured",
        }
