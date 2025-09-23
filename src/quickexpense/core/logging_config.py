"""Logging configuration for professional audit trail compliance."""

import json
import logging
import logging.handlers
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    """Audit logging configuration for CRA compliance."""

    log_level: str = Field(default="INFO", description="Log level for audit trail")
    log_format: str = Field(default="json", description="Log format (json or text)")
    max_file_size_mb: int = Field(default=10, description="Maximum log file size in MB")
    backup_count: int = Field(
        default=365, description="Number of backup files (~1 year)"
    )
    retention_years: int = Field(default=7, description="CRA retention requirement")
    audit_log_path: Path = Field(
        default=Path("logs/audit"), description="Audit log directory"
    )
    performance_log_path: Path = Field(
        default=Path("logs/performance"), description="Performance log directory"
    )
    enable_console_output: bool = Field(
        default=True, description="Enable console logging"
    )
    sanitize_sensitive_data: bool = Field(
        default=True, description="Remove sensitive data from logs"
    )

    def setup_directories(self) -> None:
        """Create log directories if they don't exist."""
        self.audit_log_path.mkdir(parents=True, exist_ok=True)
        self.performance_log_path.mkdir(parents=True, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured audit logging."""

    def __init__(self, *, sanitize_sensitive: bool = True) -> None:
        """Initialize formatter with sanitization option."""
        super().__init__()
        self.sanitize_sensitive = sanitize_sensitive
        self.sensitive_fields = {
            "access_token",
            "refresh_token",
            "api_key",
            "password",
            "client_secret",  # More specific than just "secret"
            "secret_key",  # More specific patterns
            "private_key",
            "credit_card",
            "ssn",
            "sin",
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName if record.funcName else "<unknown>",
            "line": record.lineno,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from audit records
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "stack_info",
                "exc_info",
                "exc_text",
                "message",
                "getMessage",
            }
        }

        if extra_fields:
            # Sanitize sensitive data if enabled
            if self.sanitize_sensitive:
                extra_fields = self._sanitize_data(extra_fields)

            log_entry.update(extra_fields)

            # Add entity-aware tax form information
            if "entity_type" in extra_fields:
                log_entry["tax_form"] = self._get_tax_form(extra_fields["entity_type"])

        return json.dumps(log_entry, default=self._json_serializer, ensure_ascii=False)

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove or mask sensitive data from log entries."""
        sanitized = {}
        for key, value in data.items():
            # Check if the key contains sensitive terms, but exclude performance metrics
            is_sensitive = self._is_sensitive_key(
                key
            ) and not self._is_performance_metric(key)

            if is_sensitive:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key should be considered sensitive."""
        key_lower = key.lower()
        short_term_length = 3

        # Use word boundaries for short terms like "sin" to avoid false positives
        for sensitive in self.sensitive_fields:
            if len(sensitive) <= short_term_length:  # Short terms like "sin", "ssn"
                # Use word boundary matching for short terms
                pattern = r"\b" + re.escape(sensitive) + r"\b"
                if re.search(pattern, key_lower):
                    return True
            # Use substring matching for longer terms
            elif sensitive in key_lower:
                return True
        return False

    def _is_performance_metric(self, key: str) -> bool:
        """Check if the key is a performance metric that should not be sanitized."""
        performance_metrics = {
            "processing_time_seconds",
            "total_processing_time_seconds",
            "duration_seconds",
            "response_time",
            "elapsed_time",
            "execution_time",
            "start_time",
            "end_time",
            "timestamp",
            "created_at",
            "updated_at",
        }
        return key.lower() in performance_metrics or key.lower().endswith(
            "_time_seconds"
        )

    def _get_tax_form(self, entity_type: str) -> str:
        """Get appropriate tax form for entity type."""
        tax_forms = {
            "sole_proprietorship": "T2125",
            "corporation": "T2",
            "partnership": "T5013",
        }
        return tax_forms.get(entity_type, "unknown")

    def _json_serializer(self, obj: Any) -> str:  # noqa: ANN401
        """JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        return str(obj)


def setup_audit_logging(config: LoggingConfig) -> logging.Logger:
    """Set up professional audit logging with rotation and retention."""
    # Ensure directories exist
    config.setup_directories()

    # Create audit logger
    audit_logger = logging.getLogger("quickexpense.audit")
    audit_logger.setLevel(getattr(logging, config.log_level.upper()))

    # Clear existing handlers to avoid duplicates
    audit_logger.handlers.clear()

    # Add file handler with rotation
    log_file = config.audit_log_path / "quickexpense_audit.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=config.max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
        backupCount=config.backup_count,
    )

    # Set structured formatter
    formatter = StructuredFormatter(sanitize_sensitive=config.sanitize_sensitive_data)
    file_handler.setFormatter(formatter)
    audit_logger.addHandler(file_handler)

    # Add console handler if enabled
    if config.enable_console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        audit_logger.addHandler(console_handler)

    # Prevent propagation to root logger
    audit_logger.propagate = False

    return audit_logger


def setup_performance_logging(config: LoggingConfig) -> logging.Logger:
    """Set up performance monitoring logging."""
    # Ensure directories exist
    config.setup_directories()

    # Create performance logger
    perf_logger = logging.getLogger("quickexpense.performance")
    perf_logger.setLevel(logging.INFO)

    # Clear existing handlers
    perf_logger.handlers.clear()

    # Add file handler with rotation
    log_file = config.performance_log_path / "quickexpense_performance.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=config.max_file_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
    )

    # Set structured formatter
    formatter = StructuredFormatter(sanitize_sensitive=config.sanitize_sensitive_data)
    file_handler.setFormatter(formatter)
    perf_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    perf_logger.propagate = False

    return perf_logger


def cleanup_old_logs(config: LoggingConfig) -> int:
    """Clean up logs older than retention period."""
    cutoff_time = time.time() - (config.retention_years * 365 * 24 * 60 * 60)
    removed_count = 0

    for log_dir in [config.audit_log_path, config.performance_log_path]:
        if not log_dir.exists():
            continue

        for log_file in log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    removed_count += 1
            except OSError:
                # File might be in use or have permission issues
                continue

    return removed_count
