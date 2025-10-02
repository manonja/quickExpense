"""Enhanced base agent with comprehensive logging capabilities."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from quickexpense.services.agents.base import AgentResult, BaseReceiptAgent

if TYPE_CHECKING:
    from quickexpense.services.ag2_logging import AG2StructuredLogger
    from quickexpense.services.audit_logger import AuditLogger
    from quickexpense.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


class LoggingBaseReceiptAgent(BaseReceiptAgent):
    """Enhanced base agent with structured logging capabilities."""

    def __init__(
        self,
        name: str,
        timeout_seconds: float = 2.0,
        ag2_logger: AG2StructuredLogger | None = None,
        conversation_logger: ConversationLogger | None = None,
        audit_logger: AuditLogger | None = None,
        *,
        enable_detailed_logging: bool = True,
    ) -> None:
        """Initialize enhanced agent with logging.

        Args:
            name: Name of the agent
            timeout_seconds: Maximum processing time
            ag2_logger: AG2 structured logger instance
            conversation_logger: Conversation history logger
            audit_logger: Audit logger instance
            enable_detailed_logging: Whether to enable detailed logging
        """
        super().__init__(name, timeout_seconds)
        self.ag2_logger = ag2_logger
        self.conversation_logger = conversation_logger
        self.audit_logger = audit_logger
        self.enable_detailed_logging = enable_detailed_logging
        self.correlation_id: str | None = None
        self.session_id: str | None = None

    def set_correlation_context(
        self, correlation_id: str, session_id: str | None = None
    ) -> None:
        """Set correlation context for logging."""
        self.correlation_id = correlation_id
        self.session_id = session_id

    async def process(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Process receipt with comprehensive logging.

        Args:
            receipt_data: Raw receipt data to process
            context: Optional context from previous agents

        Returns:
            AgentResult with processing outcome
        """
        start_time = time.time()
        context = context or {}

        # Extract correlation ID from context if not set
        if not self.correlation_id and "correlation_id" in context:
            self.correlation_id = context["correlation_id"]
        if not self.session_id and "session_id" in context:
            self.session_id = context["session_id"]

        # Log agent start
        self._log_agent_start(receipt_data, context)

        try:
            # Log input to conversation history
            if self.conversation_logger and self.correlation_id:
                self.conversation_logger.log_agent_message(
                    correlation_id=self.correlation_id,
                    agent_name=self.name,
                    content=f"Processing receipt with context: {json.dumps(context)}",
                    role="system",
                    session_id=self.session_id,
                )

            # Run processing with timeout
            result_data = await asyncio.wait_for(
                self._process_internal_with_logging(receipt_data, context),
                timeout=self.timeout_seconds,
            )

            processing_time = time.time() - start_time
            confidence_score = self._calculate_confidence(result_data, receipt_data)

            # Extract key results for logging
            reasoning = self._extract_reasoning(result_data)
            category = result_data.get("category")
            tax_treatment = result_data.get("tax_treatment")

            # Log successful completion
            self._log_agent_success(
                result_data=result_data,
                confidence_score=confidence_score,
                processing_time=processing_time,
                reasoning=reasoning,
                category=category,
                tax_treatment=tax_treatment,
            )

            # Create result
            result = AgentResult(
                agent_name=self.name,
                success=True,
                confidence_score=confidence_score,
                data=result_data,
                processing_time=processing_time,
                metadata=self._get_enhanced_metadata(result_data),
            )

            # Log to conversation history
            if self.conversation_logger and self.correlation_id:
                self.conversation_logger.log_agent_result(
                    correlation_id=self.correlation_id,
                    agent_result=result,
                    session_id=self.session_id,
                )

            return result

        except TimeoutError:
            processing_time = time.time() - start_time
            error_msg = f"Agent {self.name} timed out after {self.timeout_seconds}s"

            # Log timeout error
            self._log_agent_error(error_msg, "timeout", processing_time)

            result = AgentResult(
                agent_name=self.name,
                success=False,
                confidence_score=0.0,
                data={},
                processing_time=processing_time,
                error_message=error_msg,
            )

            # Log to conversation history
            if self.conversation_logger and self.correlation_id:
                self.conversation_logger.log_agent_result(
                    correlation_id=self.correlation_id,
                    agent_result=result,
                    session_id=self.session_id,
                )

            return result

        except Exception as e:  # noqa: BLE001
            processing_time = time.time() - start_time
            error_msg = f"Agent {self.name} failed: {e!s}"

            # Log exception
            self._log_agent_error(error_msg, "exception", processing_time, str(e))

            result = AgentResult(
                agent_name=self.name,
                success=False,
                confidence_score=0.0,
                data={},
                processing_time=processing_time,
                error_message=error_msg,
            )

            # Log to conversation history
            if self.conversation_logger and self.correlation_id:
                self.conversation_logger.log_agent_result(
                    correlation_id=self.correlation_id,
                    agent_result=result,
                    session_id=self.session_id,
                )

            return result

    async def _process_internal_with_logging(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Wrapper for internal processing with step logging."""
        # Log processing start
        if self.ag2_logger and self.enable_detailed_logging:
            self.ag2_logger.trace_logger.debug(
                f"[{self.name}] Starting internal processing"
            )

        # Call the actual implementation
        result = await self._process_internal(receipt_data, context)

        # Log processing steps
        if self.ag2_logger and self.enable_detailed_logging:
            self.ag2_logger.trace_logger.debug(
                f"[{self.name}] Completed internal processing with "
                f"{len(result)} result keys"
            )

        return result

    def _log_agent_start(
        self, receipt_data: dict[str, Any], context: dict[str, Any]
    ) -> None:
        """Log agent processing start."""
        if self.audit_logger and self.correlation_id:
            self.audit_logger.log_with_context(
                level="INFO",
                message=f"Agent {self.name} started processing",
                context={
                    "event_type": "agent_start",
                    "agent_name": self.name,
                    "correlation_id": self.correlation_id,
                    "session_id": self.session_id,
                    "receipt_keys": list(receipt_data.keys()),
                    "context_keys": list(context.keys()),
                },
            )

        if self.ag2_logger:
            self.ag2_logger.trace_logger.info(
                f"[{self.name}] Started processing receipt"
            )

    def _log_agent_success(
        self,
        result_data: dict[str, Any],
        confidence_score: float,
        processing_time: float,
        reasoning: str,
        category: str | None,
        tax_treatment: str | None,
    ) -> None:
        """Log successful agent completion."""
        self.logger.info(
            "Agent %s completed successfully in %.2fs (confidence: %.2f)",
            self.name,
            processing_time,
            confidence_score,
        )

        # Log to AG2 structured logger
        if self.ag2_logger:
            self.ag2_logger.log_agent_decision(
                agent_name=self.name,
                confidence=confidence_score,
                category=category,
                tax_treatment=tax_treatment,
                reasoning=reasoning,
                processing_time=processing_time,
                metadata={
                    "result_keys": list(result_data.keys()),
                    "has_validation": "tax_validation_result" in result_data,
                },
            )

        # Log to audit logger
        if self.audit_logger and self.correlation_id:
            self.audit_logger.log_with_context(
                level="INFO",
                message=f"Agent {self.name} completed successfully",
                context={
                    "event_type": "agent_success",
                    "agent_name": self.name,
                    "correlation_id": self.correlation_id,
                    "confidence_score": confidence_score,
                    "processing_time": processing_time,
                    "category": category,
                    "tax_treatment": tax_treatment,
                },
            )

    def _log_agent_error(
        self,
        error_msg: str,
        error_type: str,
        processing_time: float,
        exception_details: str | None = None,
    ) -> None:
        """Log agent errors."""
        self.logger.error(error_msg)

        # Log to AG2 structured logger
        if self.ag2_logger:
            self.ag2_logger.log_error(
                agent_name=self.name,
                error=error_msg,
                error_type=error_type,
                metadata={
                    "processing_time": processing_time,
                    "exception_details": exception_details,
                },
            )

        # Log to audit logger
        if self.audit_logger and self.correlation_id:
            self.audit_logger.log_with_context(
                level="ERROR",
                message=error_msg,
                context={
                    "event_type": "agent_error",
                    "agent_name": self.name,
                    "correlation_id": self.correlation_id,
                    "error_type": error_type,
                    "processing_time": processing_time,
                    "exception_details": exception_details,
                },
            )

    def _extract_reasoning(self, result_data: dict[str, Any]) -> str:
        """Extract reasoning from result data."""
        # Try various possible fields for reasoning
        reasoning_fields = [
            "reasoning",
            "explanation",
            "rationale",
            "cra_rule_applied",
            "notes",
        ]

        for field in reasoning_fields:
            if result_data.get(field):
                return str(result_data[field])[:500]

        return "No explicit reasoning provided"

    def _get_enhanced_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Get enhanced metadata with logging context."""
        base_metadata = super()._get_metadata(result_data)

        enhanced = {
            **base_metadata,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "logging_enabled": {
                "ag2_logger": self.ag2_logger is not None,
                "conversation_logger": self.conversation_logger is not None,
                "audit_logger": self.audit_logger is not None,
            },
        }

        # Add result-specific metadata
        if "tax_validation_result" in result_data:
            enhanced["tax_validation"] = result_data["tax_validation_result"]

        if "audit_risk" in result_data:
            enhanced["audit_risk"] = result_data["audit_risk"]

        return enhanced

    def log_inter_agent_message(
        self,
        recipient: str,
        message: str,
        confidence: float | None = None,
    ) -> None:
        """Log communication to another agent."""
        if self.ag2_logger:
            self.ag2_logger.log_inter_agent_communication(
                sender=self.name,
                recipient=recipient,
                message=message,
                communication_type="request",
                confidence=confidence,
            )

        if self.conversation_logger and self.correlation_id:
            self.conversation_logger.log_system_message(
                correlation_id=self.correlation_id,
                content=f"{self.name} -> {recipient}: {message[:200]}",
                metadata={
                    "sender": self.name,
                    "recipient": recipient,
                    "confidence": confidence,
                },
                session_id=self.session_id,
            )


def create_logging_agent(
    name: str,
    agent_class: type[BaseReceiptAgent],
    settings: Any,
    ag2_logger: AG2StructuredLogger | None = None,
    conversation_logger: ConversationLogger | None = None,
    audit_logger: AuditLogger | None = None,
    **kwargs: Any,
) -> LoggingBaseReceiptAgent:
    """Factory function to create agents with logging capabilities.

    Args:
        name: Agent name
        agent_class: The specific agent class to instantiate
        settings: Application settings
        ag2_logger: AG2 structured logger
        conversation_logger: Conversation logger
        audit_logger: Audit logger
        **kwargs: Additional arguments for the agent class

    Returns:
        Agent instance with logging capabilities
    """

    class LoggingAgent(LoggingBaseReceiptAgent, agent_class):
        """Dynamic class combining logging capabilities with specific agent."""

        def __init__(self) -> None:
            # Initialize both parent classes
            LoggingBaseReceiptAgent.__init__(
                self,
                name=name,
                timeout_seconds=kwargs.get("timeout_seconds", 2.0),
                ag2_logger=ag2_logger,
                conversation_logger=conversation_logger,
                audit_logger=audit_logger,
            )
            agent_class.__init__(self, settings, **kwargs)

    return LoggingAgent()
