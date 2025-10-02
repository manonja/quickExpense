"""Enhanced agent orchestrator with comprehensive logging."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from quickexpense.services.ag2_logging import ConsensusDecisionData
from quickexpense.services.agents.orchestrator import (
    AgentOrchestrator,
    ConsensusResult,
)

if TYPE_CHECKING:
    from quickexpense.services.ag2_logging import AG2StructuredLogger
    from quickexpense.services.agents.base import AgentResult, BaseReceiptAgent
    from quickexpense.services.audit_logger import AuditLogger
    from quickexpense.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


class LoggingAgentOrchestrator(AgentOrchestrator):
    """Enhanced orchestrator with comprehensive logging capabilities."""

    def __init__(
        self,
        data_extraction_agent: BaseReceiptAgent,
        cra_rules_agent: BaseReceiptAgent,
        tax_calculator_agent: BaseReceiptAgent,
        consensus_threshold: float = 0.75,
        ag2_logger: AG2StructuredLogger | None = None,
        conversation_logger: ConversationLogger | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        """Initialize orchestrator with logging.

        Args:
            data_extraction_agent: Agent for extracting receipt data
            cra_rules_agent: Agent for applying CRA rules and categorization
            tax_calculator_agent: Agent for tax calculations and validation
            consensus_threshold: Minimum confidence for auto-processing
            ag2_logger: AG2 structured logger
            conversation_logger: Conversation history logger
            audit_logger: Audit logger
        """
        super().__init__(
            data_extraction_agent=data_extraction_agent,
            cra_rules_agent=cra_rules_agent,
            tax_calculator_agent=tax_calculator_agent,
            consensus_threshold=consensus_threshold,
        )

        self.ag2_logger = ag2_logger
        self.conversation_logger = conversation_logger
        self.audit_logger = audit_logger

        # Track current processing context
        self.current_correlation_id: str | None = None
        self.current_session_id: str | None = None

    async def process_receipt(
        self,
        file_base64: str,
        additional_context: str | None = None,
        correlation_id: str | None = None,
    ) -> ConsensusResult:
        """Process receipt with comprehensive logging.

        Args:
            file_base64: Base64 encoded receipt file
            additional_context: Optional context for processing
            correlation_id: Optional correlation ID (will generate if not provided)

        Returns:
            ConsensusResult with final consensus data
        """
        # Generate or use provided correlation ID
        correlation_id_val = correlation_id or str(uuid.uuid4())
        self.current_correlation_id = correlation_id_val

        # Start logging session
        if self.ag2_logger:
            with self.ag2_logger.session(self.current_correlation_id) as logger_session:
                self.current_session_id = logger_session.current_session_id
                return await self._process_with_logging(file_base64, additional_context)
        else:
            return await self._process_with_logging(file_base64, additional_context)

    async def _process_with_logging(
        self,
        file_base64: str,
        additional_context: str | None = None,
    ) -> ConsensusResult:
        """Internal processing with full logging."""
        start_time = time.time()

        # Log orchestration start
        self._log_orchestration_start(additional_context)

        # Start conversation logging
        if self.conversation_logger and self.current_correlation_id:
            self.conversation_logger.start_conversation(
                correlation_id=self.current_correlation_id,
                session_id=self.current_session_id,
                metadata={
                    "additional_context": additional_context,
                    "file_size": len(file_base64),
                },
            )

            # Log user input
            if self.current_correlation_id:
                context_str = additional_context or "None"
                self.conversation_logger.log_user_input(
                    correlation_id=self.current_correlation_id,
                    content=f"Process receipt with context: {context_str}",
                    session_id=self.current_session_id,
                )

        # Set correlation context for all agents
        self._set_agent_correlation_context()

        # Create enhanced context with logging info
        context: dict[str, Any] = {
            "file_base64": file_base64,
            "additional_context": additional_context,
            "correlation_id": self.current_correlation_id,
            "session_id": self.current_session_id,
        }

        agent_results: list[AgentResult] = []

        # Phase 1: Data Extraction
        self._log_phase_start("DataExtraction", self.data_extraction_agent.name)

        extraction_result = await self.data_extraction_agent.process(
            receipt_data={"file_base64": file_base64},
            context=context,
        )
        agent_results.append(extraction_result)

        self._log_phase_complete(
            "DataExtraction",
            self.data_extraction_agent.name,
            success=extraction_result.success,
            confidence=extraction_result.confidence_score,
            processing_time=extraction_result.processing_time,
        )

        if not extraction_result.success:
            self.logger.warning("Data extraction failed, aborting pipeline")
            self._log_orchestration_failure("Data extraction failed")
            result = self._create_failure_result(
                agent_results, time.time() - start_time
            )
            await self._finalize_logging(result)
            return result

        # Log inter-agent communication
        self._log_inter_agent_handoff(
            self.data_extraction_agent.name,
            self.cra_rules_agent.name,
            extraction_result.data,
            extraction_result.confidence_score,
        )

        # Update context with extraction results
        context["extracted_data"] = extraction_result.data

        # Phase 2: CRA Rules
        self._log_phase_start("CRArulesAnalysis", self.cra_rules_agent.name)

        cra_result = await self.cra_rules_agent.process(
            receipt_data=extraction_result.data,
            context=context,
        )
        agent_results.append(cra_result)

        self._log_phase_complete(
            "CRArulesAnalysis",
            self.cra_rules_agent.name,
            success=cra_result.success,
            confidence=cra_result.confidence_score,
            processing_time=cra_result.processing_time,
        )

        # Log inter-agent communication
        if cra_result.success:
            context["cra_categorization"] = cra_result.data
            self._log_inter_agent_handoff(
                self.cra_rules_agent.name,
                self.tax_calculator_agent.name,
                cra_result.data,
                cra_result.confidence_score,
            )

        # Phase 3: Tax Calculator
        self._log_phase_start("TaxCalculation", self.tax_calculator_agent.name)

        tax_result = await self.tax_calculator_agent.process(
            receipt_data=extraction_result.data,
            context=context,
        )
        agent_results.append(tax_result)

        self._log_phase_complete(
            "TaxCalculation",
            self.tax_calculator_agent.name,
            success=tax_result.success,
            confidence=tax_result.confidence_score,
            processing_time=tax_result.processing_time,
        )

        # Calculate consensus
        processing_time = time.time() - start_time
        consensus = self._calculate_consensus_with_logging(
            agent_results, context, processing_time
        )

        # Finalize logging
        await self._finalize_logging(consensus)

        return consensus

    def _calculate_consensus_with_logging(
        self,
        agent_results: list[AgentResult],
        context: dict[str, Any],
        total_processing_time: float,
    ) -> ConsensusResult:
        """Calculate consensus with detailed logging."""
        # Call parent consensus calculation
        consensus = self._calculate_consensus(agent_results, context)
        consensus.processing_time = total_processing_time

        # Log consensus decision
        if self.ag2_logger:
            individual_scores = {
                r.agent_name: r.confidence_score for r in agent_results if r.success
            }

            decision_rationale = self._generate_consensus_rationale(
                agent_results, consensus
            )

            decision_data = ConsensusDecisionData(
                overall_confidence=consensus.overall_confidence,
                consensus_method=consensus.consensus_method,
                final_category=consensus.final_data.get("category", "Unknown"),
                final_tax_treatment=consensus.final_data.get(
                    "tax_treatment", "Unknown"
                ),
                individual_scores=individual_scores,
                review_flags=consensus.flags_for_review,
                processing_time=total_processing_time,
                requires_review=len(consensus.flags_for_review) > 0,
                decision_rationale=decision_rationale,
            )
            self.ag2_logger.log_consensus_decision(decision_data)

        self._log_orchestration_complete(consensus)

        return consensus

    def _set_agent_correlation_context(self) -> None:
        """Set correlation context on all agents if they support logging."""
        for agent in [
            self.data_extraction_agent,
            self.cra_rules_agent,
            self.tax_calculator_agent,
        ]:
            if hasattr(agent, "set_correlation_context"):
                agent.set_correlation_context(
                    self.current_correlation_id,
                    self.current_session_id,
                )

    def _log_orchestration_start(self, additional_context: str | None) -> None:
        """Log the start of orchestration."""
        if self.audit_logger:
            self.audit_logger.log_with_context(
                level="INFO",
                message="Starting multi-agent receipt processing",
                context={
                    "event_type": "orchestration_start",
                    "correlation_id": self.current_correlation_id,
                    "session_id": self.current_session_id,
                    "additional_context": additional_context,
                    "consensus_threshold": self.consensus_threshold,
                },
            )

        if self.ag2_logger:
            self.ag2_logger.trace_logger.info(
                "Orchestrator starting receipt processing (correlation_id: %s)",
                self.current_correlation_id,
            )

    def _log_phase_start(self, phase_name: str, agent_name: str) -> None:
        """Log the start of a processing phase."""
        if self.conversation_logger and self.current_correlation_id:
            self.conversation_logger.log_system_message(
                correlation_id=self.current_correlation_id,
                content=f"Starting phase: {phase_name} with agent {agent_name}",
                metadata={"phase": phase_name, "agent": agent_name},
                session_id=self.current_session_id,
            )

        logger.info("Starting phase %s with agent {agent_name}", phase_name)

    def _log_phase_complete(
        self,
        phase_name: str,
        agent_name: str,
        *,
        success: bool,
        confidence: float,
        processing_time: float,
    ) -> None:
        """Log the completion of a processing phase."""
        status = "succeeded" if success else "failed"

        if self.audit_logger:
            self.audit_logger.log_with_context(
                level="INFO" if success else "WARNING",
                message=f"Phase {phase_name} {status}",
                context={
                    "event_type": "phase_complete",
                    "correlation_id": self.current_correlation_id,
                    "phase": phase_name,
                    "agent": agent_name,
                    "success": success,
                    "confidence": confidence,
                    "processing_time": processing_time,
                },
            )

        logger.info(
            "Phase %s %s (confidence: %.2f, time: %.2fs)",
            phase_name,
            status,
            confidence,
            processing_time,
        )

    def _log_inter_agent_handoff(
        self,
        sender: str,
        recipient: str,
        data_summary: dict[str, Any],
        confidence: float,
    ) -> None:
        """Log handoff between agents."""
        # Create summary of data being passed
        summary = {
            "data_keys": list(data_summary.keys()),
            "has_category": "category" in data_summary,
            "has_tax_info": "tax_amount" in data_summary,
            "confidence": confidence,
        }

        message = f"Passing results to {recipient} (confidence: {confidence:.2f})"

        if self.ag2_logger:
            self.ag2_logger.log_inter_agent_communication(
                sender=sender,
                recipient=recipient,
                message=message,
                communication_type="handoff",
                confidence=confidence,
            )

        if self.conversation_logger and self.current_correlation_id:
            self.conversation_logger.log_system_message(
                correlation_id=self.current_correlation_id,
                content=f"{sender} → {recipient}: {message}",
                metadata=summary,
                session_id=self.current_session_id,
            )

    def _log_orchestration_failure(self, reason: str) -> None:
        """Log orchestration failure."""
        if self.audit_logger:
            self.audit_logger.log_with_context(
                level="ERROR",
                message=f"Orchestration failed: {reason}",
                context={
                    "event_type": "orchestration_failure",
                    "correlation_id": self.current_correlation_id,
                    "reason": reason,
                },
            )

    def _log_orchestration_complete(self, consensus: ConsensusResult) -> None:
        """Log orchestration completion."""
        if self.audit_logger:
            self.audit_logger.log_with_context(
                level="INFO",
                message="Multi-agent processing completed",
                context={
                    "event_type": "orchestration_complete",
                    "correlation_id": self.current_correlation_id,
                    "success": consensus.success,
                    "overall_confidence": consensus.overall_confidence,
                    "processing_time": consensus.processing_time,
                    "requires_review": len(consensus.flags_for_review) > 0,
                    "final_category": consensus.final_data.get("category"),
                },
            )

        logger.info(
            "Multi-agent processing completed in %.2fs (confidence: %.2f)",
            consensus.processing_time,
            consensus.overall_confidence,
        )

    def _generate_consensus_rationale(
        self,
        agent_results: list[AgentResult],
        consensus: ConsensusResult,
    ) -> str:
        """Generate a rationale for the consensus decision."""
        successful = [r for r in agent_results if r.success]
        failed = [r for r in agent_results if not r.success]

        rationale = (
            f"Consensus reached with {len(successful)}/{len(agent_results)} agents. "
        )

        if consensus.overall_confidence >= self.consensus_threshold:
            rationale += (
                f"Confidence ({consensus.overall_confidence:.2f}) exceeds threshold. "
            )
        else:
            rationale += (
                f"Confidence ({consensus.overall_confidence:.2f}) below threshold. "
            )

        if failed:
            failed_names = [r.agent_name for r in failed]
            rationale += f"Failed agents: {', '.join(failed_names)}. "

        if consensus.flags_for_review:
            rationale += f"Review needed: {'; '.join(consensus.flags_for_review[:2])}"

        return rationale

    async def _finalize_logging(self, result: ConsensusResult) -> None:
        """Finalize all logging for the session."""
        if self.conversation_logger:
            # Import at runtime to avoid circular dependency
            from quickexpense.models.multi_agent import (
                AgentResultResponse,
                MultiAgentReceiptResponse,
            )

            # Convert AgentResult to AgentResultResponse
            agent_result_responses = [
                AgentResultResponse(
                    agent_name=ar.agent_name,
                    success=ar.success,
                    confidence_score=ar.confidence_score,
                    processing_time=ar.processing_time,
                    error_message=ar.error_message,
                )
                for ar in result.agent_results
            ]

            # Convert to response format for logging
            response = MultiAgentReceiptResponse(
                success=result.success,
                overall_confidence=result.overall_confidence,
                consensus_method=result.consensus_method,
                processing_time=result.processing_time,
                vendor_name=result.final_data.get("vendor_name"),
                transaction_date=result.final_data.get("transaction_date"),
                total_amount=result.final_data.get("total_amount"),
                subtotal=result.final_data.get("subtotal"),
                tax_amount=result.final_data.get("tax_amount"),
                category=result.final_data.get("category"),
                deductibility_percentage=result.final_data.get(
                    "deductibility_percentage"
                ),
                qb_account=result.final_data.get("qb_account"),
                audit_risk=result.final_data.get("audit_risk"),
                agent_results=agent_result_responses,
                flags_for_review=result.flags_for_review,
                full_data=result.final_data,
            )

            if self.current_correlation_id:
                self.conversation_logger.end_conversation(
                    correlation_id=self.current_correlation_id,
                    final_result=response,
                    metadata={
                        "session_id": self.current_session_id,
                        "agent_count": len(result.agent_results),
                    },
                )

        # Get final metrics from AG2 logger
        if self.ag2_logger:
            metrics = self.ag2_logger.get_session_metrics()
            logger.info("Session metrics: %s", metrics)


def create_logging_orchestrator(
    data_extraction_agent: BaseReceiptAgent,
    cra_rules_agent: BaseReceiptAgent,
    tax_calculator_agent: BaseReceiptAgent,
    consensus_threshold: float = 0.75,
    ag2_logger: AG2StructuredLogger | None = None,
    conversation_logger: ConversationLogger | None = None,
    audit_logger: AuditLogger | None = None,
) -> LoggingAgentOrchestrator:
    """Factory function to create orchestrator with logging.

    Args:
        data_extraction_agent: Agent for extracting receipt data
        cra_rules_agent: Agent for applying CRA rules
        tax_calculator_agent: Agent for tax calculations
        consensus_threshold: Minimum confidence threshold
        ag2_logger: AG2 structured logger
        conversation_logger: Conversation logger
        audit_logger: Audit logger

    Returns:
        Orchestrator instance with logging capabilities
    """
    return LoggingAgentOrchestrator(
        data_extraction_agent=data_extraction_agent,
        cra_rules_agent=cra_rules_agent,
        tax_calculator_agent=tax_calculator_agent,
        consensus_threshold=consensus_threshold,
        ag2_logger=ag2_logger,
        conversation_logger=conversation_logger,
        audit_logger=audit_logger,
    )
