#!/usr/bin/env python3
"""Test TogetherAI integration with multi-agent receipt processing."""

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from quickexpense.core.config import get_settings
from quickexpense.services.agents import (
    AgentOrchestrator,
    CRArulesAgent,
    DataExtractionAgent,
    TaxCalculatorAgent,
)
from quickexpense.services.llm_provider import LLMProviderFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_together.log"),
    ],
)
logger = logging.getLogger(__name__)


def encode_file_to_base64(file_path: str) -> str:
    """Encode a file to base64 string."""
    with Path(file_path).open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def test_provider_configuration():
    """Test LLM provider configuration."""
    logger.info("=== Testing LLM Provider Configuration ===")

    settings = get_settings()
    logger.info(f"Primary provider: {settings.llm_provider}")
    logger.info(f"Fallback enabled: {settings.llm_fallback_enabled}")

    # Test TogetherAI provider
    try:
        together_provider = LLMProviderFactory.create(settings, "together")
        config = together_provider.get_autogen_config()
        logger.info("TogetherAI configured successfully:")
        logger.info(f"  - Model: {config['config_list'][0]['model']}")
        logger.info(f"  - API Type: {config['config_list'][0]['api_type']}")
        logger.info(f"  - Temperature: {config['config_list'][0]['temperature']}")
    except Exception as e:
        logger.error(f"TogetherAI configuration failed: {e}")

    # Test fallback to Gemini
    if settings.gemini_api_key:
        try:
            gemini_provider = LLMProviderFactory.create(settings, "gemini")
            logger.info("Gemini fallback available")
        except Exception as e:
            logger.warning(f"Gemini fallback not available: {e}")


async def test_receipt_processing(receipt_path: str):
    """Test multi-agent receipt processing with TogetherAI."""
    logger.info(f"\n=== Testing Receipt Processing: {receipt_path} ===")

    # Check if file exists
    if not Path(receipt_path).exists():
        logger.error(f"Receipt file not found: {receipt_path}")
        return

    # Encode the receipt
    try:
        file_base64 = encode_file_to_base64(receipt_path)
        logger.info(f"Encoded receipt: {Path(receipt_path).name}")
    except Exception as e:
        logger.error(f"Failed to encode receipt: {e}")
        return

    # Initialize settings and agents
    settings = get_settings()

    # Create agents
    data_agent = DataExtractionAgent(settings)
    cra_agent = CRArulesAgent(settings)
    tax_agent = TaxCalculatorAgent(settings)

    # Create orchestrator
    orchestrator = AgentOrchestrator(
        data_extraction_agent=data_agent,
        cra_rules_agent=cra_agent,
        tax_calculator_agent=tax_agent,
    )

    # Process receipt
    try:
        logger.info("Starting multi-agent processing...")
        result = await orchestrator.process_receipt(
            file_base64=file_base64,
            additional_context="Business expense receipt for testing",
        )

        logger.info("\n=== Processing Results ===")
        logger.info(f"Success: {result.success}")
        logger.info(f"Overall Confidence: {result.overall_confidence:.2f}")
        logger.info(f"Consensus Method: {result.consensus_method}")
        logger.info(f"Processing Time: {result.processing_time:.2f}s")

        if result.flags_for_review:
            logger.warning(f"Flags for Review: {result.flags_for_review}")

        # Show agent results
        logger.info("\n=== Agent Results ===")
        for agent_result in result.agent_results:
            logger.info(f"\n{agent_result.agent_name}:")
            logger.info(f"  - Success: {agent_result.success}")
            logger.info(f"  - Confidence: {agent_result.confidence_score:.2f}")
            logger.info(f"  - Processing Time: {agent_result.processing_time:.2f}s")
            logger.info(
                f"  - Provider: {agent_result.metadata.get('llm_provider', 'N/A')}"
            )
            if agent_result.error_message:
                logger.error(f"  - Error: {agent_result.error_message}")

        # Show key extracted data
        final_data = result.final_data
        logger.info("\n=== Extracted Data ===")
        logger.info(f"Vendor: {final_data.get('vendor_name')}")
        logger.info(f"Date: {final_data.get('transaction_date')}")
        # Convert string values to float for display
        total_amount = final_data.get("total_amount", 0)
        if isinstance(total_amount, str):
            try:
                total_amount = float(total_amount)
            except ValueError:
                total_amount = 0.0

        tax_amount = final_data.get("tax_amount", 0)
        if isinstance(tax_amount, str):
            try:
                tax_amount = float(tax_amount)
            except ValueError:
                tax_amount = 0.0

        logger.info(f"Total Amount: ${total_amount:.2f}")
        logger.info(f"Tax Amount: ${tax_amount:.2f}")

        logger.info("\n=== CRA Categorization ===")
        logger.info(f"Category: {final_data.get('category')}")
        logger.info(f"Deductibility: {final_data.get('deductibility_percentage')}%")
        logger.info(f"QuickBooks Account: {final_data.get('qb_account')}")
        logger.info(f"ITA Section: {final_data.get('ita_section')}")
        logger.info(f"Audit Risk: {final_data.get('audit_risk')}")

        logger.info("\n=== Tax Validation ===")
        # Convert calculated values to float for display
        calculated_gst_hst = final_data.get("calculated_gst_hst", 0)
        if isinstance(calculated_gst_hst, str):
            try:
                calculated_gst_hst = float(calculated_gst_hst)
            except ValueError:
                calculated_gst_hst = 0.0

        deductible_amount = final_data.get("deductible_amount", 0)
        if isinstance(deductible_amount, str):
            try:
                deductible_amount = float(deductible_amount)
            except ValueError:
                deductible_amount = 0.0

        logger.info(f"Calculated GST/HST: ${calculated_gst_hst:.2f}")
        logger.info(f"Deductible Amount: ${deductible_amount:.2f}")
        logger.info(f"Tax Validation Result: {final_data.get('tax_validation_result')}")

        # Save results to file
        output_file = Path("test_together_results.json")
        with output_file.open("w") as f:
            json.dump(
                {
                    "receipt_file": receipt_path,
                    "success": result.success,
                    "overall_confidence": result.overall_confidence,
                    "processing_time": result.processing_time,
                    "final_data": final_data,
                    "agent_metadata": {
                        res.agent_name: {
                            "success": res.success,
                            "confidence": res.confidence_score,
                            "time": res.processing_time,
                            "provider": res.metadata.get("llm_provider"),
                        }
                        for res in result.agent_results
                    },
                },
                f,
                indent=2,
            )
        logger.info(f"\nResults saved to: {output_file}")

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)


async def main():
    """Run all tests."""
    # Test provider configuration
    await test_provider_configuration()

    # Test with HEIC receipt
    receipt_path = "/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC"
    await test_receipt_processing(receipt_path)


if __name__ == "__main__":
    asyncio.run(main())
