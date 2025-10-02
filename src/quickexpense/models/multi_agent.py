"""Models for multi-agent receipt processing system."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentResultResponse(BaseModel):
    """Response model for individual agent results."""

    agent_name: str = Field(..., description="Name of the agent")
    success: bool = Field(..., description="Whether the agent succeeded")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the result (0-1)"
    )
    processing_time: float = Field(..., description="Time taken to process (seconds)")
    error_message: str | None = Field(
        default=None, description="Error message if agent failed"
    )


class MultiAgentReceiptResponse(BaseModel):
    """Response model for multi-agent receipt processing."""

    success: bool = Field(..., description="Whether processing succeeded")
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score"
    )

    # Extracted receipt data
    vendor_name: str | None = Field(default=None, description="Vendor name")
    transaction_date: str | None = Field(default=None, description="Transaction date")
    total_amount: float | None = Field(default=None, description="Total amount")
    subtotal: float | None = Field(default=None, description="Subtotal")
    tax_amount: float | None = Field(default=None, description="Tax amount")

    # CRA categorization
    category: str | None = Field(default=None, description="Expense category")
    deductibility_percentage: int | None = Field(
        default=None, description="Deductibility percentage"
    )
    qb_account: str | None = Field(default=None, description="QuickBooks account")
    ita_section: str | None = Field(default=None, description="ITA section reference")
    audit_risk: str | None = Field(default=None, description="Audit risk level")

    # Tax calculations
    calculated_gst_hst: float | None = Field(
        default=None, description="Calculated GST/HST amount"
    )
    deductible_amount: float | None = Field(
        default=None, description="Deductible business amount"
    )
    tax_validation_result: str | None = Field(
        default=None, description="Tax validation result"
    )

    # Processing metadata
    processing_time: float = Field(..., description="Total processing time (seconds)")
    consensus_method: str = Field(
        default="simple_average", description="Method used for consensus"
    )
    flags_for_review: list[str] = Field(
        default_factory=list, description="Reasons why manual review may be needed"
    )

    # Agent details
    agent_results: list[AgentResultResponse] = Field(
        default_factory=list, description="Individual agent results"
    )
    agent_confidence_scores: dict[str, float] = Field(
        default_factory=dict, description="Confidence scores by agent"
    )

    # Additional data for detailed view
    full_data: dict[str, Any] = Field(
        default_factory=dict, description="Complete data from all agents"
    )
