"""AG2/AutoGen structured logging integration for multi-agent systems."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import autogen

    from quickexpense.services.audit_logger import AuditLogger

# AG2/AutoGen native loggers
try:
    import autogen.runtime_logging
    from autogen import EVENT_LOGGER_NAME, TRACE_LOGGER_NAME

    AG2_AVAILABLE = True
except ImportError:
    AG2_AVAILABLE = False
    EVENT_LOGGER_NAME = "ag2.event"
    TRACE_LOGGER_NAME = "ag2.trace"

logger = logging.getLogger(__name__)


class AgentDecisionEvent(BaseModel):
    """Structured event for agent decisions."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str = "agent_decision"
    correlation_id: str
    session_id: str | None = None
    agent_name: str
    confidence_score: float
    category: str | None = None
    tax_treatment: str | None = None
    deductibility_rate: float | None = None
    reasoning: str = ""
    processing_time: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterAgentCommunication(BaseModel):
    """Log inter-agent communication events."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str = "inter_agent_communication"
    correlation_id: str
    session_id: str | None = None
    sender: str
    recipient: str
    message_preview: str
    message_length: int
    communication_type: str  # request, response, clarification
    confidence_passed: float | None = None


class ConsensusDecisionEvent(BaseModel):
    """Log consensus decision making."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str = "consensus_decision"
    correlation_id: str
    session_id: str | None = None
    overall_confidence: float
    consensus_method: str
    agent_agreement_rate: float
    final_category: str
    final_tax_treatment: str
    requires_review: bool
    review_flags: list[str] = Field(default_factory=list)
    individual_scores: dict[str, float] = Field(default_factory=dict)
    decision_rationale: str = ""
    processing_time: float


class PerformanceMetrics(BaseModel):
    """Agent performance metrics."""

    agent_name: str
    total_calls: int = 0
    total_processing_time: float = 0.0
    avg_processing_time: float = 0.0
    avg_confidence: float = 0.0
    success_rate: float = 1.0
    error_count: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_estimate: Decimal = Decimal("0.00")


class AG2StructuredLogger:
    """Enhanced structured logging for AG2 multi-agent systems."""

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        db_path: Path | None = None,
        enable_ag2_native: bool = True,
        enable_runtime_logging: bool = True,
    ):
        """Initialize AG2 structured logger."""
        self.audit_logger = audit_logger
        self.db_path = db_path or Path("data/agent_logs.db")
        self.enable_ag2_native = enable_ag2_native and AG2_AVAILABLE
        self.enable_runtime_logging = enable_runtime_logging and AG2_AVAILABLE

        # Current session tracking
        self.current_session_id: str | None = None
        self.current_correlation_id: str | None = None

        # Performance tracking
        self.agent_metrics: dict[str, PerformanceMetrics] = defaultdict(
            lambda: PerformanceMetrics(agent_name="unknown")
        )

        # Initialize AG2 native loggers if available
        if self.enable_ag2_native:
            self._setup_ag2_native_logging()

    def _setup_ag2_native_logging(self) -> None:
        """Set up AG2's native trace and event logging."""
        # Trace logger for human-readable debug info
        self.trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
        if not self.trace_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - AG2-TRACE - %(levelname)s - %(message)s"
                )
            )
            self.trace_logger.addHandler(handler)
            self.trace_logger.setLevel(logging.DEBUG)

        # Event logger for structured machine-readable events
        self.event_logger = logging.getLogger(EVENT_LOGGER_NAME)
        if not self.event_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))  # JSON output
            self.event_logger.addHandler(handler)
            self.event_logger.setLevel(logging.INFO)

    @contextmanager
    def session(self, correlation_id: str):
        """Context manager for a logging session with correlation ID."""
        old_correlation = self.current_correlation_id
        self.current_correlation_id = correlation_id

        # Start AG2 runtime logging if enabled
        if self.enable_runtime_logging:
            try:
                import autogen.runtime_logging

                self.current_session_id = autogen.runtime_logging.start(
                    config={
                        "dbname": str(self.db_path),
                        "tags": ["quickexpense", correlation_id],
                    }
                )
                logger.info(
                    f"Started AG2 runtime logging session: {self.current_session_id}"
                )
            except Exception as e:
                logger.warning(f"Could not start AG2 runtime logging: {e}")
                self.current_session_id = None

        try:
            yield self
        finally:
            # Stop runtime logging
            if self.enable_runtime_logging and self.current_session_id:
                try:
                    import autogen.runtime_logging

                    autogen.runtime_logging.stop()
                    logger.info("Stopped AG2 runtime logging session")
                except Exception as e:
                    logger.warning(f"Error stopping AG2 runtime logging: {e}")

            self.current_correlation_id = old_correlation
            self.current_session_id = None

    def log_agent_decision(
        self,
        agent_name: str,
        confidence: float,
        category: str | None = None,
        tax_treatment: str | None = None,
        reasoning: str = "",
        processing_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an agent's decision with full context."""
        event = AgentDecisionEvent(
            correlation_id=self.current_correlation_id or "unknown",
            session_id=self.current_session_id,
            agent_name=agent_name,
            confidence_score=confidence,
            category=category,
            tax_treatment=tax_treatment,
            reasoning=reasoning[:500],  # Limit reasoning length
            processing_time=processing_time,
            metadata=metadata or {},
        )

        # Log to multiple destinations
        self._log_event(event)

        # Update metrics
        metrics = self.agent_metrics[agent_name]
        metrics.agent_name = agent_name
        metrics.total_calls += 1
        metrics.total_processing_time += processing_time
        metrics.avg_processing_time = (
            metrics.total_processing_time / metrics.total_calls
        )

        # Track confidence
        current_sum = metrics.avg_confidence * (metrics.total_calls - 1)
        metrics.avg_confidence = (current_sum + confidence) / metrics.total_calls

    def log_inter_agent_communication(
        self,
        sender: str,
        recipient: str,
        message: str,
        communication_type: str = "request",
        confidence: float | None = None,
    ) -> None:
        """Log communication between agents."""
        event = InterAgentCommunication(
            correlation_id=self.current_correlation_id or "unknown",
            session_id=self.current_session_id,
            sender=sender,
            recipient=recipient,
            message_preview=message[:200],
            message_length=len(message),
            communication_type=communication_type,
            confidence_passed=confidence,
        )

        self._log_event(event)

    def log_consensus_decision(
        self,
        overall_confidence: float,
        consensus_method: str,
        final_category: str,
        final_tax_treatment: str,
        individual_scores: dict[str, float],
        requires_review: bool,
        review_flags: list[str],
        processing_time: float,
        decision_rationale: str = "",
    ) -> None:
        """Log the final consensus decision."""
        # Calculate agreement rate
        scores = list(individual_scores.values())
        avg_score = sum(scores) / len(scores) if scores else 0
        agreement_rate = (
            1.0
            - (sum(abs(s - avg_score) for s in scores) / len(scores) if scores else 0)
            / avg_score
            if avg_score > 0
            else 0
        )

        event = ConsensusDecisionEvent(
            correlation_id=self.current_correlation_id or "unknown",
            session_id=self.current_session_id,
            overall_confidence=overall_confidence,
            consensus_method=consensus_method,
            agent_agreement_rate=agreement_rate,
            final_category=final_category,
            final_tax_treatment=final_tax_treatment,
            requires_review=requires_review,
            review_flags=review_flags,
            individual_scores=individual_scores,
            decision_rationale=decision_rationale[:500],
            processing_time=processing_time,
        )

        self._log_event(event)

    def log_error(
        self,
        agent_name: str,
        error: str,
        error_type: str = "processing_error",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log agent errors."""
        error_event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "agent_error",
            "correlation_id": self.current_correlation_id or "unknown",
            "session_id": self.current_session_id,
            "agent_name": agent_name,
            "error": str(error),
            "error_type": error_type,
            "metadata": metadata or {},
        }

        # Log error
        self._log_raw_event(error_event)

        # Update error metrics
        metrics = self.agent_metrics[agent_name]
        metrics.error_count += 1
        metrics.success_rate = (
            (metrics.total_calls - metrics.error_count) / metrics.total_calls
            if metrics.total_calls > 0
            else 0
        )

    def log_token_usage(
        self,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model: str,
        cost: Decimal | None = None,
    ) -> None:
        """Log LLM token usage and costs."""
        usage_event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "token_usage",
            "correlation_id": self.current_correlation_id or "unknown",
            "session_id": self.current_session_id,
            "agent_name": agent_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": float(cost) if cost else None,
        }

        self._log_raw_event(usage_event)

        # Update metrics
        metrics = self.agent_metrics[agent_name]
        metrics.token_usage["prompt_tokens"] = (
            metrics.token_usage.get("prompt_tokens", 0) + prompt_tokens
        )
        metrics.token_usage["completion_tokens"] = (
            metrics.token_usage.get("completion_tokens", 0) + completion_tokens
        )
        metrics.token_usage["total_tokens"] = (
            metrics.token_usage.get("total_tokens", 0) + total_tokens
        )
        if cost:
            metrics.cost_estimate += cost

    def _log_event(self, event: BaseModel) -> None:
        """Log a structured event to all configured destinations."""
        event_dict = event.model_dump(mode="json")

        # Convert datetime to string
        if "timestamp" in event_dict:
            event_dict["timestamp"] = event_dict["timestamp"].isoformat()

        self._log_raw_event(event_dict)

    def _log_raw_event(self, event_dict: dict[str, Any]) -> None:
        """Log raw event dictionary to all destinations."""
        # Log to audit logger if available
        if self.audit_logger:
            self.audit_logger.log_with_context(
                level="INFO",
                message=f"AG2 Event: {event_dict.get('event_type', 'unknown')}",
                context=event_dict,
            )

        # Log to AG2 event logger
        if self.enable_ag2_native and hasattr(self, "event_logger"):
            self.event_logger.info(json.dumps(event_dict))

        # Log to standard logger
        logger.info(f"AG2 Event: {json.dumps(event_dict)}")

    def get_session_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the current session."""
        return {
            "correlation_id": self.current_correlation_id,
            "session_id": self.current_session_id,
            "agent_metrics": {
                name: metrics.model_dump()
                for name, metrics in self.agent_metrics.items()
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_session_events(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve all events for a session from the runtime database."""
        if not self.enable_runtime_logging or not self.db_path.exists():
            return []

        session_to_query = session_id or self.current_session_id
        if not session_to_query:
            return []

        events = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT timestamp, source, message, json_state
                    FROM chat_completions
                    WHERE session_id = ?
                    ORDER BY timestamp
                    """,
                    (session_to_query,),
                )
                for row in cursor:
                    events.append(
                        {
                            "timestamp": row[0],
                            "source": row[1],
                            "message": row[2],
                            "state": json.loads(row[3]) if row[3] else {},
                        }
                    )
        except Exception as e:
            logger.error(f"Error retrieving session events: {e}")

        return events


# Factory function for easy creation
def create_ag2_logger(
    audit_logger: AuditLogger | None = None,
    enable_native_logging: bool = True,
) -> AG2StructuredLogger:
    """Create an AG2 structured logger instance."""
    return AG2StructuredLogger(
        audit_logger=audit_logger,
        enable_ag2_native=enable_native_logging,
    )
