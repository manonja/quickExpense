#!/usr/bin/env python3
"""Test comprehensive logging integration with multi-agent receipt processing."""

import asyncio
import base64
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from quickexpense.core.config import get_settings
from quickexpense.services.agents import (
    CRArulesAgent,
    DataExtractionAgent,
    TaxCalculatorAgent,
)
from quickexpense.services.logging_integration import (
    create_logging_integration,
    print_logging_config,
)

# Configure root logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_logging_integration.log"),
    ],
)
logger = logging.getLogger(__name__)


def encode_file_to_base64(file_path: str) -> str:
    """Encode a file to base64 string."""
    with Path(file_path).open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def test_logging_system() -> None:
    """Test the complete logging system integration."""
    logger.info("=== Testing Comprehensive Logging System ===")

    # Print current configuration
    print_logging_config()

    # Create correlation ID for this test
    correlation_id = f"test-{int(time.time())}"
    logger.info("Test correlation ID: %s", correlation_id)

    # Initialize logging integration
    logging_integration = create_logging_integration(correlation_id)

    # Get settings
    settings = get_settings()

    # Create original agents
    data_agent = DataExtractionAgent(settings)
    cra_agent = CRArulesAgent(settings)
    tax_agent = TaxCalculatorAgent(settings)

    logger.info("\nOriginal agents created:")
    logger.info("  - %s", data_agent.get_agent_info())
    logger.info("  - %s", cra_agent.get_agent_info())
    logger.info("  - %s", tax_agent.get_agent_info())

    # Wrap agents with logging
    logging_data_agent, logging_cra_agent, logging_tax_agent = (
        logging_integration.create_logging_agents(data_agent, cra_agent, tax_agent)
    )

    logger.info("\nLogging-enabled agents created")

    # Create logging orchestrator
    orchestrator = logging_integration.create_logging_orchestrator(
        logging_data_agent,
        logging_cra_agent,
        logging_tax_agent,
    )

    logger.info("\nLogging orchestrator created")

    # Test receipt path
    receipt_path = "/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC"
    if not Path(receipt_path).exists():
        logger.error("Receipt file not found: %s", receipt_path)
        return

    # Encode receipt
    try:
        file_base64 = encode_file_to_base64(receipt_path)
        logger.info("\nEncoded receipt: %s", Path(receipt_path).name)
        logger.info("File size: %d base64 characters", len(file_base64))
    except Exception as e:
        logger.error("Failed to encode receipt: %s", e)
        return

    # Process receipt with full logging
    logger.info("\n=== Starting Receipt Processing with Logging ===")
    try:
        result = await orchestrator.process_receipt(
            file_base64=file_base64,
            additional_context="Test receipt for logging validation",
            correlation_id=correlation_id,
        )

        logger.info("\n=== Processing Results ===")
        logger.info("Success: %s", result.success)
        logger.info("Overall Confidence: %.2f", result.overall_confidence)
        logger.info("Consensus Method: %s", result.consensus_method)
        logger.info("Processing Time: %.2fs", result.processing_time)
        logger.info("Flags for Review: %s", result.flags_for_review)

        # Log agent results
        logger.info("\n=== Agent Results ===")
        for agent_result in result.agent_results:
            logger.info("\n%s:", agent_result.agent_name)
            logger.info("  - Success: %s", agent_result.success)
            logger.info("  - Confidence: %.2f", agent_result.confidence_score)
            logger.info("  - Processing Time: %.2fs", agent_result.processing_time)
            if agent_result.error_message:
                logger.error("  - Error: %s", agent_result.error_message)

        # Log final data
        logger.info("\n=== Final Extracted Data ===")
        final_data = result.final_data
        logger.info("Vendor: %s", final_data.get("vendor_name"))
        logger.info("Total Amount: $%s", final_data.get("total_amount"))
        logger.info("Category: %s", final_data.get("category"))
        logger.info("Tax Treatment: %s", final_data.get("tax_treatment"))
        logger.info("Audit Risk: %s", final_data.get("audit_risk"))

    except Exception as e:
        logger.error("Processing failed: %s", e, exc_info=True)

    # Get performance report
    logger.info("\n=== Performance Report ===")
    performance_report = logging_integration.get_performance_report()
    if performance_report:
        logger.info(json.dumps(performance_report, indent=2, default=str))
    else:
        logger.info("Performance monitoring not available")

    # Check conversation history
    if logging_integration.conversation_logger:
        logger.info("\n=== Conversation History ===")
        conversation = logging_integration.conversation_logger.get_conversation(
            correlation_id
        )
        if conversation:
            logger.info("Conversation found: %s", conversation.correlation_id)
            logger.info("Start time: %s", conversation.start_time)
            logger.info("End time: %s", conversation.end_time)
            logger.info("Total entries: %s", len(conversation.entries))

            # Log first few entries
            for i, entry in enumerate(conversation.entries[:5]):
                logger.info(
                    "\nEntry %d: %s (%s) - Confidence: %s",
                    i + 1,
                    entry.agent_name,
                    entry.role,
                    entry.confidence_score,
                )

            # Check recent conversations
            recent = logging_integration.conversation_logger.get_recent_conversations(
                limit=5
            )
            logger.info("\nRecent conversations: %s", len(recent))

    # Check AG2 session metrics
    if logging_integration.ag2_logger:
        logger.info("\n=== AG2 Session Metrics ===")
        metrics = logging_integration.ag2_logger.get_session_metrics()
        logger.info(json.dumps(metrics, indent=2, default=str))

    # Test analytics queries
    if logging_integration.performance_analytics:
        logger.info("\n=== Analytics Queries ===")

        # Agent performance
        agent_perf = logging_integration.performance_analytics.get_agent_performance()
        logger.info("\nAgent Performance:")
        for agent_name, stats in agent_perf.items():
            logger.info("  %s:", agent_name)
            logger.info("    - Total requests: %s", stats.total_requests)
            logger.info("    - Success rate: %.2f%%", stats.success_rate * 100)
            logger.info("    - Avg time: %.2fs", stats.avg_processing_time)
            logger.info("    - Avg confidence: %.2f", stats.avg_confidence_score)

        # System performance
        system_perf = logging_integration.performance_analytics.get_system_performance()
        logger.info("\nSystem Performance:")
        logger.info("  - Total sessions: %s", system_perf.total_sessions)
        success_rate = (
            system_perf.successful_sessions / system_perf.total_sessions
            if system_perf.total_sessions > 0
            else 0
        )
        logger.info("  - Success rate: %.2f%%", success_rate * 100)
        logger.info("  - Avg session time: %.2fs", system_perf.avg_session_time)

        # Token usage
        try:
            token_usage = (
                logging_integration.performance_analytics.get_token_usage_report()
            )
            if not token_usage.empty:
                logger.info("\nToken Usage by Model:")
                logger.info(token_usage.to_string())
        except Exception as e:
            logger.warning("Could not get token usage: %s", e)

    logger.info("\n=== Logging Test Complete ===")


async def test_monitoring_endpoints() -> None:
    """Test the monitoring API endpoints."""
    logger.info("\n\n=== Testing Monitoring Endpoints ===")

    import httpx

    base_url = "http://localhost:8000/api/v1/monitoring"

    async with httpx.AsyncClient() as client:
        # Test performance endpoint
        try:
            response = await client.get(f"{base_url}/performance?hours=1")
            if response.status_code == 200:
                logger.info("✓ Performance endpoint working")
                data = response.json()
                logger.info("  - Total sessions: %s", data.get("total_sessions", 0))
                logger.info(
                    "  - Success rate: %.2%%", data.get("success_rate", 0) * 100
                )
            else:
                logger.warning(
                    "✗ Performance endpoint returned %s", response.status_code
                )
        except Exception as e:
            logger.error("✗ Performance endpoint failed: %s", e)

        # Test conversations endpoint
        try:
            response = await client.get(f"{base_url}/conversations?limit=5")
            if response.status_code == 200:
                logger.info("✓ Conversations endpoint working")
                conversations = response.json()
                logger.info("  - Found %s conversations", len(conversations))
            else:
                logger.warning(
                    "✗ Conversations endpoint returned %s", response.status_code
                )
        except Exception as e:
            logger.error("✗ Conversations endpoint failed: %s", e)

        # Test agent performance endpoint
        try:
            agent_url = f"{base_url}/agents/DataExtractionAgent/performance"
            response = await client.get(f"{agent_url}?hours=1")
            if response.status_code == 200:
                logger.info("✓ Agent performance endpoint working")
                data = response.json()
                logger.info("  - Total requests: %s", data.get("total_requests", 0))
            else:
                logger.warning(
                    "✗ Agent performance endpoint returned %s", response.status_code
                )
        except Exception as e:
            logger.error("✗ Agent performance endpoint failed: %s", e)

        # Test error analysis endpoint
        try:
            response = await client.get(f"{base_url}/errors?hours=24")
            if response.status_code == 200:
                logger.info("✓ Error analysis endpoint working")
                data = response.json()
                logger.info("  - Total errors: %s", data.get("total_errors", 0))
            else:
                logger.warning(
                    "✗ Error analysis endpoint returned %s", response.status_code
                )
        except Exception as e:
            logger.error("✗ Error analysis endpoint failed: %s", e)

    logger.info("\n=== Monitoring Endpoint Test Complete ===")


async def main() -> None:
    """Run all tests."""
    # Test the logging system
    await test_logging_system()

    # Give some time for async writes to complete
    await asyncio.sleep(2)

    # Test monitoring endpoints (only if server is running)
    logger.info("\nTo test monitoring endpoints, ensure the server is running:")
    logger.info("  uv run fastapi dev src/quickexpense/main.py")
    logger.info("\nThen uncomment the line below:")
    # await test_monitoring_endpoints()

    logger.info("\n=== All Tests Complete ===")
    logger.info("\nCheck the following for results:")
    logger.info("  - test_logging_integration.log (this test output)")
    logger.info("  - data/conversation_history.db (conversation logs)")
    logger.info("  - data/agent_logs.db (AG2 runtime logs)")
    logger.info("  - API endpoints at http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())
