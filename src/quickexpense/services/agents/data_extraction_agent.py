"""Data extraction agent using autogen and Gemini for receipt processing."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import autogen

from quickexpense.services.file_processor import FileProcessorService
from quickexpense.services.gemini import GeminiService
from quickexpense.services.llm_provider import LLMProviderFactory

from .base import BaseReceiptAgent

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIDENCE_SCORE = 0.8
COMPLETENESS_BONUS = 0.02
COMPLETENESS_VALIDATION_BONUS = 0.05
TOTAL_TOLERANCE_CENTS = 0.02  # 2 cent tolerance for totals


class DataExtractionAgent(BaseReceiptAgent):
    """Agent specialized in extracting structured data from receipt images."""

    def __init__(
        self,
        settings: Settings,
        name: str = "DataExtractionAgent",
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the data extraction agent.

        Args:
            settings: Application settings with Gemini configuration
            name: Agent name
            timeout_seconds: Processing timeout
        """
        super().__init__(name, timeout_seconds)
        self.settings = settings
        self.file_processor = FileProcessorService()

        # Use Gemini for image processing
        self.gemini_service = GeminiService(settings)

        # Configure LLM provider for validation/formatting only
        self.llm_provider = LLMProviderFactory.create(settings)
        self.llm_config = self.llm_provider.get_autogen_config()

        # Create the autogen assistant agent
        self.agent = autogen.AssistantAgent(
            name="receipt_data_extractor",
            llm_config=self.llm_config,
            system_message=self._get_extraction_system_message(),
        )

    async def _process_internal(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract receipt data using Gemini for image processing.

        Args:
            receipt_data: Should contain 'file_base64' key
            context: Processing context

        Returns:
            Dictionary with extracted receipt data
        """
        file_base64 = receipt_data.get("file_base64")
        if not file_base64:
            msg = "No file_base64 provided in receipt_data"
            raise ValueError(msg)

        additional_context = context.get("additional_context")

        try:
            # Use Gemini service directly for image extraction
            self.logger.info("Using Gemini for image extraction")
            extracted_receipt = await self.gemini_service.extract_receipt_data(
                file_base64=file_base64,
                additional_context=additional_context,
            )

            # Convert ExtractedReceipt model to dict with JSON-compatible format
            extracted_data = extracted_receipt.model_dump(mode="json")

            # Validate the extracted data structure
            self._validate_extracted_data(extracted_data)

            # Add processing metadata
            extracted_data["processing_metadata"] = {
                "original_file_type": "image",  # Gemini handles file type detection
                "agent_name": self.name,
                "extraction_provider": "gemini",  # Always Gemini for images
                "llm_provider": self.llm_provider.provider_name,  # For agent config
            }

            # Optionally use autogen for data validation/formatting
            # This is text-only processing, no images
            if self.settings.llm_provider == "together":
                extracted_data = await self._validate_with_agent(extracted_data)

            return extracted_data

        except Exception as e:
            self.logger.error("Failed to extract receipt data: %s", e)
            raise

    def _build_extraction_prompt(self, additional_context: str | None) -> str:
        """Build the extraction prompt for the agent."""
        base_prompt = """
Extract all information from this receipt image and return it as a JSON object
matching this exact schema:

{
    "vendor_name": "string (required)",
    "vendor_address": "string or null",
    "vendor_phone": "string or null",
    "transaction_date": "YYYY-MM-DD format (required)",
    "receipt_number": "string or null",
    "payment_method": "cash|credit_card|debit_card|check|bank_transfer|other",
    "line_items": [
        {
            "description": "string",
            "quantity": "number (default 1)",
            "unit_price": "number",
            "total_price": "number"
        }
    ],
    "subtotal": "number (required)",
    "tax_amount": "number (default 0)",
    "tip_amount": "number (default 0)",
    "total_amount": "number (required)",
    "currency": "3-letter code (default USD)",
    "notes": "string or null",
    "confidence_score": "number between 0-1 indicating extraction confidence"
}

CRITICAL INSTRUCTIONS:
1. Extract ALL line items visible on the receipt
2. Ensure all monetary values are positive numbers
3. For HOTEL RECEIPTS: Use the actual amount charged, NOT the balance
   - If you see 'Balance: 0.00' and a credit card charge amount, use the charge amount
   - Look for 'Amount:', 'Card charged:', or 'Total charged:' values
4. Verify that subtotal + tax_amount + tip_amount = total_amount
5. Use the most appropriate payment_method based on receipt content
6. Set confidence_score based on image clarity and extraction certainty
7. For dates, use today's date if not visible on receipt
8. Currency should be a 3-letter ISO code (USD, CAD, EUR, etc.)
9. For multi-day hotel stays, include each day's charges as separate line items

Return ONLY the JSON object, no additional text or explanations.
"""

        if additional_context:
            base_prompt += f"\n\nAdditional context: {additional_context}"

        return base_prompt

    def _validate_extracted_data(self, data: dict[str, Any]) -> None:
        """Validate the extracted data structure.

        Args:
            data: Extracted data to validate

        Raises:
            ValueError: If data is invalid
        """
        required_fields = [
            "vendor_name",
            "transaction_date",
            "subtotal",
            "total_amount",
        ]

        for field in required_fields:
            if field not in data:
                msg = f"Missing required field: {field}"
                raise ValueError(msg)

        # Validate amounts are positive
        amount_fields = ["subtotal", "total_amount", "tax_amount", "tip_amount"]
        for field in amount_fields:
            if field in data and data[field] is not None:
                try:
                    amount = float(data[field])
                    if amount < 0:
                        msg = f"Amount field {field} must be positive, got {amount}"
                        raise ValueError(msg)
                except (ValueError, TypeError) as e:
                    msg = f"Invalid amount for {field}: {data[field]}"
                    raise ValueError(msg) from e

        # Validate confidence score
        if "confidence_score" in data:
            try:
                confidence = float(data["confidence_score"])
                if not 0.0 <= confidence <= 1.0:
                    msg = f"Confidence score must be between 0-1, got {confidence}"
                    raise ValueError(msg)
            except (ValueError, TypeError) as e:
                msg = f"Invalid confidence score: {data['confidence_score']}"
                raise ValueError(msg) from e

    def _calculate_confidence(
        self,
        result_data: dict[str, Any],
        receipt_data: dict[str, Any],  # noqa: ARG002
    ) -> float:
        """Calculate confidence score for the extraction.

        Args:
            result_data: Extracted data
            receipt_data: Original receipt data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with the model's own confidence score if available
        base_confidence = result_data.get("confidence_score", DEFAULT_CONFIDENCE_SCORE)

        # Adjust based on data completeness
        completeness_bonus = 0.0

        # Check for vendor information
        if result_data.get("vendor_name"):
            completeness_bonus += 0.05
        if result_data.get("vendor_address"):
            completeness_bonus += COMPLETENESS_BONUS

        # Check for line items
        line_items = result_data.get("line_items", [])
        if line_items:
            completeness_bonus += 0.05
            if len(line_items) > 1:
                completeness_bonus += 0.03

        # Check for payment method
        if (
            result_data.get("payment_method")
            and result_data["payment_method"] != "other"
        ):
            completeness_bonus += COMPLETENESS_BONUS

        # Check for receipt number
        if result_data.get("receipt_number"):
            completeness_bonus += COMPLETENESS_BONUS

        # Mathematical consistency check
        try:
            subtotal = float(result_data.get("subtotal", 0))
            tax_amount = float(result_data.get("tax_amount", 0))
            tip_amount = float(result_data.get("tip_amount", 0))
            total_amount = float(result_data.get("total_amount", 0))

            calculated_total = subtotal + tax_amount + tip_amount
            if abs(calculated_total - total_amount) < TOTAL_TOLERANCE_CENTS:
                completeness_bonus += COMPLETENESS_VALIDATION_BONUS
        except (ValueError, TypeError):
            # Mathematical inconsistency, reduce confidence
            completeness_bonus -= 0.1

        final_confidence = min(base_confidence + completeness_bonus, 1.0)
        return max(final_confidence, 0.0)  # type: ignore[no-any-return]

    def _get_extraction_system_message(self) -> str:
        """Get the system message for the autogen agent."""
        return """
You are a specialized receipt data extraction agent. Your only job is to analyze
receipt images
and extract structured data with high accuracy. You must:

1. Extract ALL visible information from receipts accurately
2. Return data in the exact JSON format specified
3. Ensure mathematical consistency in amounts
4. Handle special cases like hotel receipts properly
5. Provide appropriate confidence scores

Focus on accuracy and completeness. If something is unclear, use reasonable defaults
but adjust your confidence score accordingly.
"""

    def _get_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Get metadata about the extraction process."""
        metadata = super()._get_metadata(result_data)
        metadata.update(
            {
                "llm_provider": self.llm_provider.provider_name,
                "model_used": self.llm_config["config_list"][0]["model"],
                "extraction_fields": len(result_data.keys()),
                "line_items_count": len(result_data.get("line_items", [])),
            }
        )
        return metadata

    async def _validate_with_agent(
        self, extracted_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Optionally validate/enhance extracted data using TogetherAI agent.

        Args:
            extracted_data: Data extracted by Gemini

        Returns:
            Validated/enhanced data
        """
        # Create validation prompt with JSON data only (no images)
        validation_prompt = f"""
Please validate and enhance this receipt data extracted by vision AI.
Fix any obvious errors and ensure mathematical consistency.

Extracted Data:
{json.dumps(extracted_data, indent=2)}

Return the corrected/validated JSON data only.
"""

        user_proxy = autogen.UserProxyAgent(
            name="user",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )

        try:
            # Use TogetherAI for text-based validation
            response = await user_proxy.a_initiate_chat(
                self.agent,
                message=validation_prompt,
                max_turns=1,
            )

            last_message = response.chat_history[-1]["content"]

            try:
                validated_data = json.loads(last_message)
                self.logger.info("Data validated by TogetherAI agent")
                return validated_data  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                # If validation fails, return original data
                self.logger.warning("Agent validation failed, using original data")
                return extracted_data

        except Exception as e:  # noqa: BLE001 # Intentional: agent robustness
            self.logger.warning("Agent validation error: %s", e, exc_info=True)
            return extracted_data
