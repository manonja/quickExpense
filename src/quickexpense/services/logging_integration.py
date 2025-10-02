"""Integration module for comprehensive logging system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quickexpense.core.config import get_settings
from quickexpense.services.ag2_logging import create_ag2_logger
from quickexpense.services.agents.logging_base import LoggingBaseReceiptAgent
from quickexpense.services.agents.logging_orchestrator import (
    create_logging_orchestrator,
)
from quickexpense.services.audit_logger import get_audit_logger
from quickexpense.services.conversation_logger import create_conversation_logger
from quickexpense.services.performance_analytics import create_performance_analytics

if TYPE_CHECKING:
    from quickexpense.services.agents import (
        CRArulesAgent,
        DataExtractionAgent,
        TaxCalculatorAgent,
    )

logger = logging.getLogger(__name__)


class LoggingIntegration:
    """Central integration point for all logging components."""

    def __init__(self, correlation_id: str | None = None):
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
    ) -> tuple[
        LoggingBaseReceiptAgent, LoggingBaseReceiptAgent, LoggingBaseReceiptAgent
    ]:
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

        # Create wrapper classes that combine logging with original agents
        class LoggingDataExtractionAgent(
            LoggingBaseReceiptAgent, type(data_extraction_agent)
        ):
            def __init__(agent_self) -> None:
                LoggingBaseReceiptAgent.__init__(
                    agent_self,
                    name=data_extraction_agent.name,
                    timeout_seconds=data_extraction_agent.timeout_seconds,
                    ag2_logger=(
                        self.ag2_logger if self.settings.log_agent_reasoning else None
                    ),
                    conversation_logger=self.conversation_logger,
                    audit_logger=self.audit_logger,
                    enable_detailed_logging=self.settings.log_agent_reasoning,
                )
                # Copy attributes from original agent
                for attr, value in data_extraction_agent.__dict__.items():
                    if not attr.startswith("_"):
                        setattr(agent_self, attr, value)

        class LoggingCRArulesAgent(LoggingBaseReceiptAgent, type(cra_rules_agent)):
            def __init__(agent_self) -> None:
                LoggingBaseReceiptAgent.__init__(
                    agent_self,
                    name=cra_rules_agent.name,
                    timeout_seconds=cra_rules_agent.timeout_seconds,
                    ag2_logger=(
                        self.ag2_logger if self.settings.log_agent_reasoning else None
                    ),
                    conversation_logger=self.conversation_logger,
                    audit_logger=self.audit_logger,
                    enable_detailed_logging=self.settings.log_agent_reasoning,
                )
                # Copy attributes from original agent
                for attr, value in cra_rules_agent.__dict__.items():
                    if not attr.startswith("_"):
                        setattr(agent_self, attr, value)

        class LoggingTaxCalculatorAgent(
            LoggingBaseReceiptAgent, type(tax_calculator_agent)
        ):
            def __init__(agent_self) -> None:
                LoggingBaseReceiptAgent.__init__(
                    agent_self,
                    name=tax_calculator_agent.name,
                    timeout_seconds=tax_calculator_agent.timeout_seconds,
                    ag2_logger=(
                        self.ag2_logger if self.settings.log_agent_reasoning else None
                    ),
                    conversation_logger=self.conversation_logger,
                    audit_logger=self.audit_logger,
                    enable_detailed_logging=self.settings.log_agent_reasoning,
                )
                # Copy attributes from original agent
                for attr, value in tax_calculator_agent.__dict__.items():
                    if not attr.startswith("_"):
                        setattr(agent_self, attr, value)

        return (
            LoggingDataExtractionAgent(),
            LoggingCRArulesAgent(),
            LoggingTaxCalculatorAgent(),
        )

    def create_logging_orchestrator(
        self,
        data_extraction_agent: LoggingBaseReceiptAgent,
        cra_rules_agent: LoggingBaseReceiptAgent,
        tax_calculator_agent: LoggingBaseReceiptAgent,
        consensus_threshold: float = 0.75,
    ):
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
            from quickexpense.services.agents import AgentOrchestrator

            return AgentOrchestrator(
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
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
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
    logger.info(f"AG2 Logging: {settings.enable_ag2_logging}")
    logger.info(f"Runtime Logging: {settings.enable_runtime_logging}")
    logger.info(f"Conversation Logging: {settings.enable_conversation_logging}")
    logger.info(f"Performance Monitoring: {settings.enable_performance_monitoring}")
    logger.info(f"AG2 Trace Level: {settings.ag2_trace_level}")
    logger.info(f"AG2 Event Level: {settings.ag2_event_level}")
    logger.info(f"Agent Reasoning Logs: {settings.log_agent_reasoning}")
    logger.info(f"Inter-Agent Communication: {settings.log_inter_agent_communication}")
    logger.info(f"Token Usage Tracking: {settings.log_token_usage}")
    logger.info(f"Consensus Decision Logs: {settings.log_consensus_decisions}")
    logger.info(f"Log Retention: {settings.log_retention_days} days")
    logger.info("=========================================")
