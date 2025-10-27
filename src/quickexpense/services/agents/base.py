"""Base classes for the multi-agent receipt processing system."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from quickexpense.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AgentResult(BaseModel):
    """Result from an individual agent."""

    agent_name: str = Field(..., description="Name of the agent")
    success: bool = Field(default=True, description="Whether the agent succeeded")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the result (0-1)"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific result data"
    )
    processing_time: float = Field(
        default=0.0, description="Time taken to process (seconds)"
    )
    error_message: str | None = Field(
        default=None, description="Error message if agent failed"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional agent metadata"
    )


class BaseReceiptAgent(ABC):
    """Base class for all receipt processing agents."""

    def __init__(self, name: str, timeout_seconds: float = 2.0) -> None:
        """Initialize the agent.

        Args:
            name: Name of the agent
            timeout_seconds: Maximum time to spend processing (default 2 seconds)
        """
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.rate_limiter: RateLimiter | None = None  # Set by subclasses if needed

    async def process(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Process receipt data with timeout handling.

        Args:
            receipt_data: Raw receipt data to process
            context: Optional context from previous agents

        Returns:
            AgentResult with the processing outcome
        """
        start_time = time.time()
        context = context or {}

        try:
            # Run the actual processing with timeout
            result_data = await asyncio.wait_for(
                self._process_internal(receipt_data, context),
                timeout=self.timeout_seconds,
            )

            processing_time = time.time() - start_time
            confidence_score = self._calculate_confidence(result_data, receipt_data)

            self.logger.info(
                "Agent %s completed successfully in %.2fs (confidence: %.2f)",
                self.name,
                processing_time,
                confidence_score,
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                confidence_score=confidence_score,
                data=result_data,
                processing_time=processing_time,
                metadata=self._get_metadata(result_data),
            )

        except TimeoutError:
            processing_time = time.time() - start_time
            error_msg = f"Agent {self.name} timed out after {self.timeout_seconds}s"
            self.logger.warning(error_msg)

            return AgentResult(
                agent_name=self.name,
                success=False,
                confidence_score=0.0,
                data={},
                processing_time=processing_time,
                error_message=error_msg,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Agent {self.name} failed: {e!s}"
            self.logger.exception("Agent %s failed with exception", self.name)

            return AgentResult(
                agent_name=self.name,
                success=False,
                confidence_score=0.0,
                data={},
                processing_time=processing_time,
                error_message=error_msg,
            )

    @abstractmethod
    async def _process_internal(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Internal processing method to be implemented by each agent.

        Args:
            receipt_data: Raw receipt data to process
            context: Context from previous agents

        Returns:
            Dictionary containing the agent's processing results
        """

    @abstractmethod
    def _calculate_confidence(
        self,
        result_data: dict[str, Any],
        receipt_data: dict[str, Any],
    ) -> float:
        """Calculate confidence score for the result.

        Args:
            result_data: The agent's processing results
            receipt_data: Original receipt data

        Returns:
            Confidence score between 0.0 and 1.0
        """

    def _get_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Get additional metadata about the processing.

        Args:
            result_data: The agent's processing results

        Returns:
            Dictionary with metadata (can be overridden by subclasses)
        """
        return {
            "agent_version": "1.0.0",
            "result_keys": list(result_data.keys()),
        }

    def get_agent_info(self) -> dict[str, Any]:
        """Get information about this agent.

        Returns:
            Dictionary with agent information
        """
        return {
            "name": self.name,
            "timeout_seconds": self.timeout_seconds,
            "agent_type": self.__class__.__name__,
        }

    def set_correlation_context(
        self, correlation_id: str, session_id: str | None = None
    ) -> None:
        """Set correlation context for logging (default implementation does nothing).

        Args:
            correlation_id: Correlation ID for tracking related operations
            session_id: Optional session ID
        """
        # Default implementation does nothing
        # Logging-enabled agents can override this method
        # Store the context if needed by subclasses
        self._correlation_id = correlation_id
        self._session_id = session_id

    def check_rate_limit(self) -> None:
        """Check rate limit before agent operation (if rate limiter is configured).

        This method should be called by subclasses before making API calls.
        If rate limiting is needed, subclasses should initialize self.rate_limiter.

        Raises:
            ValueError: If daily quota exceeded
        """
        if self.rate_limiter is not None:
            self.logger.debug(
                "Checking rate limit for %s agent", self.__class__.__name__
            )
            self.rate_limiter.check_and_wait()
