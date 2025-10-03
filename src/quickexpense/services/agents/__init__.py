"""Multi-agent system for receipt processing with CRA compliance."""

from .base import AgentResult, BaseReceiptAgent
from .cra_rules_agent import CRArulesAgent
from .data_extraction_agent import DataExtractionAgent
from .orchestrator import AgentOrchestrator, ConsensusResult
from .tax_calculator_agent import TaxCalculatorAgent

__all__ = [
    "AgentOrchestrator",
    "AgentResult",
    "BaseReceiptAgent",
    "CRArulesAgent",
    "ConsensusResult",
    "DataExtractionAgent",
    "TaxCalculatorAgent",
]
