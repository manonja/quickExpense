"""Integration module for comprehensive logging system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quickexpense.core.config import get_settings
from quickexpense.services.ag2_logging import create_ag2_logger
from quickexpense.services.agents.logging_orchestrator import (
    LoggingAgentOrchestrator,
    create_logging_orchestrator,
)
from quickexpense.services.agents.logging_wrapper import LoggingAgentWrapper
from quickexpense.services.audit_logger import get_audit_logger
from quickexpense.services.conversation_logger import create_conversation_logger
from quickexpense.services.performance_analytics import create_performance_analytics

if TYPE_CHECKING:
    from quickexpense.services.agents import (
        CRArulesAgent,
        DataExtractionAgent,
        TaxCalculatorAgent,
    )
    from quickexpense.services.agents.base import BaseReceiptAgent

logger = logging.getLogger(__name__)


class LoggingIntegration:
    """Central integration point for all logging components."""

    def __init__(self, correlation_id: str | None = None) -> None:
        """Initialize logging integration."""
        self.settings = get_settings()
        self.correlation_id = correlation_id

        # Initialize logging components based on configuration
        self.audit_logger = get_audit_logger() if self.settings.debug else None

        self.ag2_logger = None
        if self.settings.enable_ag2_logging:
            self.ag2_logger = create_ag2_logger(
                audit_logger=self.audit_logger,
                enable_native_logging=self.settings.enable_ag2_logging,
            )
            self._configure_ag2_logging_levels()

        self.conversation_logger = None
        if self.settings.enable_conversation_logging:
            self.conversation_logger = create_conversation_logger(
                db_path=Path(self.settings.conversation_db_path)
            )

        self.performance_analytics = None
        if self.settings.enable_performance_monitoring:
            self.performance_analytics = create_performance_analytics(
                conversation_db_path=Path(self.settings.conversation_db_path),
                ag2_runtime_db_path=Path(self.settings.logging_db_path),
            )

    def _configure_ag2_logging_levels(self) -> None:
        """Configure AG2 logging levels from settings."""
        if not self.ag2_logger:
            return

        # Set trace logger level
        if hasattr(self.ag2_logger, "trace_logger"):
            level = getattr(
                logging, self.settings.ag2_trace_level.upper(), logging.DEBUG
            )
            self.ag2_logger.trace_logger.setLevel(level)

        # Set event logger level
        if hasattr(self.ag2_logger, "event_logger"):
            level = getattr(
                logging, self.settings.ag2_event_level.upper(), logging.INFO
            )
            self.ag2_logger.event_logger.setLevel(level)

    def create_logging_agents(
        self,
        data_extraction_agent: DataExtractionAgent,
        cra_rules_agent: CRArulesAgent,
        tax_calculator_agent: TaxCalculatorAgent,
    ) -> tuple[Any, Any, Any]:
        """Wrap agents with logging capabilities."""
        # Check if logging features are enabled
        if not any(
            [
                self.settings.enable_ag2_logging,
                self.settings.enable_conversation_logging,
                self.audit_logger,
            ]
        ):
            # Return original agents if no logging is enabled
            return data_extraction_agent, cra_rules_agent, tax_calculator_agent

        # Create wrappers for each agent
        wrapped_data_agent = LoggingAgentWrapper(
            agent=data_extraction_agent,
            ag2_logger=self.ag2_logger if self.settings.log_agent_reasoning else None,
            conversation_logger=self.conversation_logger,
            audit_logger=self.audit_logger,
            enable_detailed_logging=self.settings.log_agent_reasoning,
        )

        wrapped_cra_agent = LoggingAgentWrapper(
            agent=cra_rules_agent,
            ag2_logger=self.ag2_logger if self.settings.log_agent_reasoning else None,
            conversation_logger=self.conversation_logger,
            audit_logger=self.audit_logger,
            enable_detailed_logging=self.settings.log_agent_reasoning,
        )

        wrapped_tax_agent = LoggingAgentWrapper(
            agent=tax_calculator_agent,
            ag2_logger=self.ag2_logger if self.settings.log_agent_reasoning else None,
            conversation_logger=self.conversation_logger,
            audit_logger=self.audit_logger,
            enable_detailed_logging=self.settings.log_agent_reasoning,
        )

        return (
            wrapped_data_agent,
            wrapped_cra_agent,
            wrapped_tax_agent,
        )

    def create_logging_orchestrator(
        self,
        data_extraction_agent: BaseReceiptAgent,
        cra_rules_agent: BaseReceiptAgent,
        tax_calculator_agent: BaseReceiptAgent,
        consensus_threshold: float = 0.75,
    ) -> LoggingAgentOrchestrator:
        """Create orchestrator with logging capabilities."""
        if not any(
            [
                self.settings.enable_ag2_logging,
                self.settings.enable_conversation_logging,
                self.audit_logger,
                self.settings.log_inter_agent_communication,
                self.settings.log_consensus_decisions,
            ]
        ):
            # Use regular orchestrator if no logging features are enabled
            from quickexpense.services.agents.orchestrator import AgentOrchestrator

            return AgentOrchestrator(  # type: ignore[return-value]
                data_extraction_agent=data_extraction_agent,
                cra_rules_agent=cra_rules_agent,
                tax_calculator_agent=tax_calculator_agent,
                consensus_threshold=consensus_threshold,
            )

        return create_logging_orchestrator(
            data_extraction_agent=data_extraction_agent,
            cra_rules_agent=cra_rules_agent,
            tax_calculator_agent=tax_calculator_agent,
            consensus_threshold=consensus_threshold,
            ag2_logger=(
                self.ag2_logger if self.settings.log_inter_agent_communication else None
            ),
            conversation_logger=self.conversation_logger,
            audit_logger=self.audit_logger,
        )

    def get_performance_report(self) -> dict[str, Any] | None:
        """Get current performance report if monitoring is enabled."""
        if not self.performance_analytics:
            return None

        try:
            system_stats = self.performance_analytics.get_system_performance()
            return system_stats.model_dump()
        except Exception as e:  # noqa: BLE001
            logger.error("Error generating performance report: %s", e)
            return None

    def cleanup(self) -> None:
        """Clean up logging resources."""
        # Close any open database connections or files


def create_logging_integration(
    correlation_id: str | None = None,
) -> LoggingIntegration:
    """Factory function to create logging integration.

    Args:
        correlation_id: Optional correlation ID for tracking

    Returns:
        LoggingIntegration instance
    """
    return LoggingIntegration(correlation_id=correlation_id)


# Environment variable mappings for quick configuration
ENV_VAR_MAPPINGS = """
# QuickExpense Logging Configuration

# Enable/disable logging features
ENABLE_AG2_LOGGING=true
ENABLE_RUNTIME_LOGGING=true
ENABLE_CONVERSATION_LOGGING=true
ENABLE_PERFORMANCE_MONITORING=true

# Logging levels
AG2_TRACE_LEVEL=DEBUG
AG2_EVENT_LEVEL=INFO
LOG_LEVEL=INFO

# Database paths
LOGGING_DB_PATH=data/agent_logs.db
CONVERSATION_DB_PATH=data/conversation_history.db

# Logging features
LOG_AGENT_REASONING=true
LOG_INTER_AGENT_COMMUNICATION=true
LOG_TOKEN_USAGE=true
LOG_CONSENSUS_DECISIONS=true

# Performance settings
PERFORMANCE_SAMPLING_RATE=1.0
LOG_RETENTION_DAYS=2555
"""


def print_logging_config() -> None:
    """Print current logging configuration for debugging."""
    settings = get_settings()

    logger.info("=== QuickExpense Logging Configuration ===")
    logger.info("AG2 Logging: %s", settings.enable_ag2_logging)
    logger.info("Runtime Logging: %s", settings.enable_runtime_logging)
    logger.info("Conversation Logging: %s", settings.enable_conversation_logging)
    logger.info("Performance Monitoring: %s", settings.enable_performance_monitoring)
    logger.info("AG2 Trace Level: %s", settings.ag2_trace_level)
    logger.info("AG2 Event Level: %s", settings.ag2_event_level)
    logger.info("Agent Reasoning Logs: %s", settings.log_agent_reasoning)
    logger.info("Inter-Agent Communication: %s", settings.log_inter_agent_communication)
    logger.info("Token Usage Tracking: %s", settings.log_token_usage)
    logger.info("Consensus Decision Logs: %s", settings.log_consensus_decisions)
    logger.info("Log Retention: %s days", settings.log_retention_days)
    logger.info("=========================================")
