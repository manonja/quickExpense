"""Agent wrapper for adding logging capabilities to existing agents."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from quickexpense.services.agents.base import AgentResult

if TYPE_CHECKING:
    from quickexpense.services.ag2_logging import AG2StructuredLogger
    from quickexpense.services.agents.base import BaseReceiptAgent
    from quickexpense.services.audit_logger import AuditLogger
    from quickexpense.services.conversation_logger import ConversationLogger


class LoggingAgentWrapper:
    """Wrapper that adds logging capabilities to any agent."""

    def __init__(
        self,
        agent: BaseReceiptAgent,
        ag2_logger: AG2StructuredLogger | None = None,
        conversation_logger: ConversationLogger | None = None,
        audit_logger: AuditLogger | None = None,
        *,
        enable_detailed_logging: bool = True,
    ) -> None:
        """Initialize the logging wrapper.

        Args:
            agent: The agent to wrap
            ag2_logger: AG2 structured logger instance
            conversation_logger: Conversation history logger
            audit_logger: Audit logger instance
            enable_detailed_logging: Whether to enable detailed logging
        """
        self._wrapped_agent = agent
        self.ag2_logger = ag2_logger
        self.conversation_logger = conversation_logger
        self.audit_logger = audit_logger
        self.enable_detailed_logging = enable_detailed_logging
        self.correlation_id: str | None = None
        self.session_id: str | None = None

        # Copy agent attributes
        self.name = agent.name
        self.timeout_seconds = agent.timeout_seconds
        self.logger = agent.logger

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
                    content=f"Processing receipt with context: {context}",
                    role="system",
                    session_id=self.session_id,
                )

            # Call the wrapped agent's process method
            result = await self._wrapped_agent.process(receipt_data, context)

            # Extract key results for logging
            processing_time = time.time() - start_time
            reasoning = self._extract_reasoning(result.data)
            category = result.data.get("category")
            tax_treatment = result.data.get("tax_treatment")

            # Log successful completion
            if result.success:
                self._log_agent_success(
                    result_data=result.data,
                    confidence_score=result.confidence_score,
                    processing_time=processing_time,
                    reasoning=reasoning,
                    category=category,
                    tax_treatment=tax_treatment,
                )
            else:
                self._log_agent_error(
                    result.error_message or "Unknown error",
                    "processing_error",
                    processing_time,
                )

            # Log to conversation history
            if self.conversation_logger and self.correlation_id:
                try:
                    self.conversation_logger.log_agent_result(
                        correlation_id=self.correlation_id,
                        agent_result=result,
                        session_id=self.session_id,
                    )
                except AttributeError as e:
                    # Handle the isoformat error more gracefully
                    self.logger.warning(
                        "Error logging agent result to conversation history: %s", str(e)
                    )
                    # Log a simplified version without problematic fields
                    self.conversation_logger.log_agent_message(
                        correlation_id=self.correlation_id,
                        agent_name=result.agent_name,
                        content=(
                            f"Result: success={result.success}, "
                            f"confidence={result.confidence_score}"
                        ),
                        role="assistant",
                        confidence_score=result.confidence_score,
                        processing_time=result.processing_time,
                        metadata={
                            "success": result.success,
                            "error": result.error_message,
                            "result_keys": (
                                list(result.data.keys()) if result.data else []
                            ),
                        },
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
                try:
                    self.conversation_logger.log_agent_result(
                        correlation_id=self.correlation_id,
                        agent_result=result,
                        session_id=self.session_id,
                    )
                except AttributeError as e:
                    # Handle the isoformat error more gracefully
                    self.logger.warning("Error logging failed agent result: %s", str(e))

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

        if self.ag2_logger and hasattr(self.ag2_logger, "trace_logger"):
            self.ag2_logger.trace_logger.info(
                "[%s] Started processing receipt", self.name
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

    # Delegate all other attributes to the wrapped agent
    def __getattr__(self, name: str) -> Any:  # noqa: ANN401  # Dynamic proxy pattern
        """Delegate attribute access to the wrapped agent."""
        return getattr(self._wrapped_agent, name)

    # Methods required by the agent interface
    def get_agent_info(self) -> dict[str, Any]:
        """Get agent information."""
        return self._wrapped_agent.get_agent_info()

    async def _process_internal(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate to wrapped agent."""
        return await self._wrapped_agent._process_internal(receipt_data, context)

    def _calculate_confidence(
        self, result_data: dict[str, Any], receipt_data: dict[str, Any]
    ) -> float:
        """Delegate to wrapped agent."""
        return self._wrapped_agent._calculate_confidence(result_data, receipt_data)

    def _get_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to wrapped agent."""
        return self._wrapped_agent._get_metadata(result_data)  # noqa: SLF001
