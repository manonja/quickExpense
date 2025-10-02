"""Agent orchestrator for coordinating multi-agent receipt processing."""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from .base import AgentResult, BaseReceiptAgent  # noqa: TCH001

logger = logging.getLogger(__name__)

# Constants
LARGE_EXPENSE_THRESHOLD = 1000  # Dollar amount threshold for flagging large expenses


class ConsensusResult(BaseModel):
    """Result of the multi-agent consensus process."""

    success: bool = Field(default=True, description="Whether consensus was reached")
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score"
    )
    final_data: dict[str, Any] = Field(
        default_factory=dict, description="Consensus data from all agents"
    )
    agent_results: list[AgentResult] = Field(
        default_factory=list, description="Individual agent results"
    )
    processing_time: float = Field(
        default=0.0, description="Total processing time (seconds)"
    )
    consensus_method: str = Field(
        default="simple_average", description="Method used for consensus"
    )
    flags_for_review: list[str] = Field(
        default_factory=list, description="Reasons why manual review may be needed"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional processing metadata"
    )


class AgentOrchestrator:
    """Orchestrates the multi-agent receipt processing workflow."""

    def __init__(
        self,
        data_extraction_agent: BaseReceiptAgent,
        cra_rules_agent: BaseReceiptAgent,
        tax_calculator_agent: BaseReceiptAgent,
        consensus_threshold: float = 0.75,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            data_extraction_agent: Agent for extracting receipt data
            cra_rules_agent: Agent for applying CRA rules and categorization
            tax_calculator_agent: Agent for tax calculations and validation
            consensus_threshold: Minimum confidence for auto-processing
        """
        self.data_extraction_agent = data_extraction_agent
        self.cra_rules_agent = cra_rules_agent
        self.tax_calculator_agent = tax_calculator_agent
        self.consensus_threshold = consensus_threshold
        self.logger = logging.getLogger(__name__)

    async def process_receipt(
        self,
        file_base64: str,
        additional_context: str | None = None,
    ) -> ConsensusResult:
        """Process a receipt through all agents and reach consensus.

        Args:
            file_base64: Base64 encoded receipt file
            additional_context: Optional context for processing

        Returns:
            ConsensusResult with the final consensus data
        """
        start_time = time.time()
        agent_results: list[AgentResult] = []
        context: dict[str, Any] = {
            "file_base64": file_base64,
            "additional_context": additional_context,
        }

        self.logger.info("Starting multi-agent receipt processing")

        # Phase 1: Data Extraction Agent
        extraction_result = await self.data_extraction_agent.process(
            receipt_data={"file_base64": file_base64},
            context=context,
        )
        agent_results.append(extraction_result)

        if not extraction_result.success:
            self.logger.warning("Data extraction failed, aborting pipeline")
            return self._create_failure_result(agent_results, time.time() - start_time)

        # Update context with extraction results
        context["extracted_data"] = extraction_result.data

        # Phase 2: CRA Rules Agent
        cra_result = await self.cra_rules_agent.process(
            receipt_data=extraction_result.data,
            context=context,
        )
        agent_results.append(cra_result)

        # Update context with CRA results (continue even if this agent fails)
        if cra_result.success:
            context["cra_categorization"] = cra_result.data

        # Phase 3: Tax Calculator Agent
        tax_result = await self.tax_calculator_agent.process(
            receipt_data=extraction_result.data,
            context=context,
        )
        agent_results.append(tax_result)

        # Calculate consensus
        processing_time = time.time() - start_time
        consensus = self._calculate_consensus(agent_results, context)
        consensus.processing_time = processing_time

        self.logger.info(
            "Multi-agent processing completed in %.2fs (confidence: %.2f)",
            processing_time,
            consensus.overall_confidence,
        )

        return consensus

    def _calculate_consensus(
        self,
        agent_results: list[AgentResult],
        context: dict[str, Any],
    ) -> ConsensusResult:
        """Calculate consensus from agent results.

        Args:
            agent_results: Results from all agents
            context: Processing context

        Returns:
            ConsensusResult with consensus data
        """
        successful_agents = [r for r in agent_results if r.success]

        if not successful_agents:
            return self._create_failure_result(agent_results, 0.0)

        # Simple average of confidence scores for now
        confidence_scores = [r.confidence_score for r in successful_agents]
        overall_confidence = sum(confidence_scores) / len(confidence_scores)

        # Merge data from all successful agents
        final_data = self._merge_agent_data(successful_agents, context)

        # Determine if manual review is needed
        flags_for_review = self._generate_review_flags(
            agent_results, overall_confidence
        )

        return ConsensusResult(
            success=len(successful_agents) > 0,
            overall_confidence=overall_confidence,
            final_data=final_data,
            agent_results=agent_results,
            consensus_method="simple_average",
            flags_for_review=flags_for_review,
            metadata=self._generate_consensus_metadata(agent_results),
        )

    def _merge_agent_data(
        self,
        successful_agents: list[AgentResult],
        context: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Merge data from successful agents into final result.

        Args:
            successful_agents: List of successful agent results
            context: Processing context

        Returns:
            Merged data dictionary
        """
        final_data: dict[str, Any] = {}

        # Start with extracted receipt data
        extraction_agent = next(
            (r for r in successful_agents if r.agent_name == "DataExtractionAgent"),
            None,
        )
        if extraction_agent:
            final_data.update(extraction_agent.data)

        # Add CRA categorization
        cra_agent = next(
            (r for r in successful_agents if r.agent_name == "CRArulesAgent"),
            None,
        )
        if cra_agent:
            final_data.update(
                {
                    "category": cra_agent.data.get("category"),
                    "deductibility_percentage": cra_agent.data.get(
                        "deductibility_percentage"
                    ),
                    "qb_account": cra_agent.data.get("qb_account"),
                    "tax_treatment": cra_agent.data.get("tax_treatment"),
                    "ita_section": cra_agent.data.get("ita_section"),
                    "audit_risk": cra_agent.data.get("audit_risk"),
                    "cra_rule_applied": cra_agent.data.get("rule_applied"),
                }
            )

        # Add tax calculations
        tax_agent = next(
            (r for r in successful_agents if r.agent_name == "TaxCalculatorAgent"),
            None,
        )
        if tax_agent:
            final_data.update(
                {
                    "calculated_gst_hst": tax_agent.data.get("calculated_gst_hst"),
                    "deductible_amount": tax_agent.data.get("deductible_amount"),
                    "tax_validation_result": tax_agent.data.get("validation_result"),
                }
            )

        # Add agent confidence scores
        final_data["agent_confidence_scores"] = {
            agent.agent_name: agent.confidence_score for agent in successful_agents
        }

        return final_data

    def _generate_review_flags(
        self,
        agent_results: list[AgentResult],
        overall_confidence: float,
    ) -> list[str]:
        """Generate flags indicating why manual review might be needed.

        Args:
            agent_results: Results from all agents
            overall_confidence: Overall confidence score

        Returns:
            List of review flag messages
        """
        flags: list[str] = []

        # Low overall confidence
        if overall_confidence < self.consensus_threshold:
            flags.append(
                f"Low confidence ({overall_confidence:.2f} < "
                f"{self.consensus_threshold})"
            )

        # Failed agents
        failed_agents = [r for r in agent_results if not r.success]
        if failed_agents:
            failed_names = [r.agent_name for r in failed_agents]
            flags.append(f"Failed agents: {', '.join(failed_names)}")

        # High audit risk (would be determined by CRA agent)
        cra_agent = next(
            (r for r in agent_results if r.agent_name == "CRArulesAgent"),
            None,
        )
        if cra_agent and cra_agent.success:
            audit_risk = cra_agent.data.get("audit_risk")
            if audit_risk == "HIGH":
                flags.append("High audit risk expense category")

        # Large amount (might need special attention)
        extraction_agent = next(
            (r for r in agent_results if r.agent_name == "DataExtractionAgent"),
            None,
        )
        if extraction_agent and extraction_agent.success:
            total_amount = extraction_agent.data.get("total_amount", 0)
            if (
                isinstance(total_amount, int | float)
                and total_amount > LARGE_EXPENSE_THRESHOLD
            ):
                flags.append(f"Large expense amount (${total_amount:.2f})")

        return flags

    def _generate_consensus_metadata(
        self,
        agent_results: list[AgentResult],
    ) -> dict[str, Any]:
        """Generate metadata about the consensus process.

        Args:
            agent_results: Results from all agents

        Returns:
            Metadata dictionary
        """
        successful_count = sum(1 for r in agent_results if r.success)
        total_processing_time = sum(r.processing_time for r in agent_results)

        return {
            "total_agents": len(agent_results),
            "successful_agents": successful_count,
            "total_agent_processing_time": total_processing_time,
            "agent_processing_times": {
                r.agent_name: r.processing_time for r in agent_results
            },
            "orchestrator_version": "1.0.0",
        }

    def _create_failure_result(
        self,
        agent_results: list[AgentResult],
        processing_time: float,
    ) -> ConsensusResult:
        """Create a failure result when no agents succeed.

        Args:
            agent_results: Results from failed agents
            processing_time: Total processing time

        Returns:
            ConsensusResult indicating failure
        """
        return ConsensusResult(
            success=False,
            overall_confidence=0.0,
            final_data={},
            agent_results=agent_results,
            processing_time=processing_time,
            consensus_method="failure",
            flags_for_review=["All agents failed to process receipt"],
            metadata=self._generate_consensus_metadata(agent_results),
        )

    def get_orchestrator_info(self) -> dict[str, Any]:
        """Get information about the orchestrator configuration.

        Returns:
            Dictionary with orchestrator information
        """
        return {
            "consensus_threshold": self.consensus_threshold,
            "agents": [
                self.data_extraction_agent.get_agent_info(),
                self.cra_rules_agent.get_agent_info(),
                self.tax_calculator_agent.get_agent_info(),
            ],
            "orchestrator_version": "1.0.0",
        }
