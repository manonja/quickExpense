"""Gemini AI service for receipt processing."""

from __future__ import annotations

import base64
import json
import logging
import time
from io import BytesIO
from typing import TYPE_CHECKING, Any

import google.generativeai as genai
from PIL import Image

from quickexpense.models.receipt import ExtractedReceipt, PaymentMethod
from quickexpense.services.file_processor import (
    FileProcessingError,
    FileProcessorService,
    FileType,
)
from quickexpense.services.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for processing receipts using Google Gemini AI."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Gemini service."""
        self.settings = settings
        self.file_processor = FileProcessorService()
        genai.configure(api_key=settings.gemini_api_key)  # type: ignore[attr-defined]

        # Initialize rate limiter for Gemini API
        self.rate_limiter = RateLimiter.get_instance("gemini", settings)

        # Configure the model with JSON schema response
        self.model = genai.GenerativeModel(  # type: ignore[attr-defined]
            model_name=settings.gemini_model,
            generation_config={  # type: ignore[arg-type]
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            },
        )

    async def extract_receipt_data(
        self,
        file_base64: str,
        additional_context: str | None = None,
        file_type: FileType | str | None = None,
    ) -> ExtractedReceipt:
        """Extract receipt data from a base64 encoded file (image or PDF).

        Args:
            file_base64: Base64 encoded file data (image or PDF)
            additional_context: Optional context to help with extraction
            file_type: Optional file type hint (auto-detected if not provided)

        Returns:
            ExtractedReceipt: Extracted receipt data

        Raises:
            ValueError: If file decoding or processing fails
            FileProcessingError: If file type is unsupported or corrupted
            ValidationError: If extracted data doesn't match expected schema
        """
        start_time = time.time()

        try:
            # Convert string file type to enum if needed
            if isinstance(file_type, str):
                file_type = FileType.from_extension(file_type)

            # Process file (handles PDF to image conversion if needed)
            processed_file = await self.file_processor.process_file(
                file_base64, file_type
            )

            # Log processing info
            if processed_file.original_file_type.is_pdf:
                logger.info(
                    "Converted PDF to image for processing (pages: %s)",
                    processed_file.processing_metadata.get("pdf_pages", "unknown"),
                )

            # Decode the processed image
            image_data = base64.b64decode(processed_file.content)
            image = Image.open(BytesIO(image_data))

            # Build the prompt
            prompt = self._build_extraction_prompt(additional_context)

            # Check rate limit before API call (may wait or raise ValueError)
            self.rate_limiter.check_and_wait()
            logger.debug("Rate limit check passed for Gemini API")

            # Process the image with Gemini
            response = self.model.generate_content([prompt, image])

            if not response.text:
                msg = "No response from Gemini model"
                raise ValueError(msg)

            # Parse JSON response
            try:
                extracted_data = json.loads(response.text)
                logger.debug("Gemini extracted data type: %s", type(extracted_data))
                logger.debug("Gemini extracted data: %s", extracted_data)
            except json.JSONDecodeError as e:
                msg = f"Failed to parse Gemini response as JSON: {response.text}"
                raise ValueError(msg) from e

            # Handle case where Gemini returns a list instead of dict
            if isinstance(extracted_data, list):
                if len(extracted_data) > 0 and isinstance(extracted_data[0], dict):
                    logger.warning("Gemini returned list, using first item")
                    extracted_data = extracted_data[0]
                else:
                    msg = f"Gemini returned invalid list format: {extracted_data}"
                    raise ValueError(msg)
            elif not isinstance(extracted_data, dict):
                msg = f"Gemini returned invalid data type: {type(extracted_data)}"
                raise TypeError(msg)

            # Validate and create ExtractedReceipt model
            receipt = ExtractedReceipt(**extracted_data)

            # Add processing metadata
            processing_time = time.time() - start_time
            logger.info(
                "Successfully extracted receipt data from %s in %.2f seconds",
                processed_file.original_file_type.value,
                processing_time,
            )

            return receipt

        except FileProcessingError:
            raise
        except (OSError, ValueError) as e:
            msg = f"Failed to decode or process file: {e}"
            raise ValueError(msg) from e

    def _build_extraction_prompt(self, additional_context: str | None) -> str:
        """Build the prompt for receipt extraction."""
        base_prompt = (
            "Extract all information from this receipt image and return "
            "it as a JSON object matching this schema:\n\n"
            "{\n"
            '    "vendor_name": "string (required)",\n'
            '    "vendor_address": "string or null",\n'
            '    "vendor_phone": "string or null",\n'
            '    "transaction_date": "YYYY-MM-DD format (required)",\n'
            '    "receipt_number": "string or null",\n'
            '    "payment_method": "cash|credit_card|debit_card|check|'
            'bank_transfer|other",\n'
            '    "line_items": [\n'
            "        {\n"
            '            "description": "string",\n'
            '            "quantity": "number (default 1)",\n'
            '            "unit_price": "number",\n'
            '            "total_price": "number"\n'
            "        }\n"
            "    ],\n"
            '    "subtotal": "number (required)",\n'
            '    "tax_amount": "number (default 0)",\n'
            '    "tip_amount": "number (default 0)",\n'
            '    "total_amount": "number (required)",\n'
            '    "currency": "3-letter code (default USD)",\n'
            '    "notes": "string or null",\n'
            '    "confidence_score": "number between 0-1 indicating '
            'extraction confidence"\n'
            "}\n\n"
            "Important instructions:\n"
            "1. Extract ALL line items visible on the receipt\n"
            "2. Ensure all monetary values are positive numbers\n"
            "3. For HOTEL RECEIPTS: Use the actual amount charged to the credit card, "
            "NOT the balance\n"
            "   - If you see 'Balance: 0.00' and a credit card charge amount, "
            "use the charge amount\n"
            "   - Look for 'Amount:', 'Card charged:', or 'Total charged:' values\n"
            "4. Verify that subtotal + tax_amount + tip_amount = total_amount\n"
            "5. Use the most appropriate payment_method based on receipt content\n"
            "6. Set confidence_score based on image clarity and extraction certainty\n"
            "7. If any required field cannot be determined, use reasonable defaults\n"
            "8. For dates, use today's date if not visible on receipt\n"
            "9. Currency should be a 3-letter ISO code (USD, EUR, GBP, etc.)\n"
            "10. For multi-day hotel stays, include each day's charges as "
            "separate line items"
        )

        if additional_context:
            base_prompt += f"\n\nAdditional context: {additional_context}"

        return base_prompt

    def _create_line_items_schema(self) -> dict[str, Any]:
        """Create Pydantic-compatible JSON schema for line items."""
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "minLength": 1},
                    "quantity": {"type": "number", "minimum": 0, "default": 1},
                    "unit_price": {"type": "number", "minimum": 0},
                    "total_price": {"type": "number", "minimum": 0},
                },
                "required": ["description", "unit_price", "total_price"],
            },
        }

    def _create_receipt_schema(self) -> dict[str, Any]:
        """Create the full receipt extraction schema."""
        return {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "minLength": 1},
                "vendor_address": {"type": ["string", "null"]},
                "vendor_phone": {"type": ["string", "null"]},
                "transaction_date": {"type": "string", "format": "date"},
                "receipt_number": {"type": ["string", "null"]},
                "payment_method": {
                    "type": "string",
                    "enum": [e.value for e in PaymentMethod],
                },
                "line_items": self._create_line_items_schema(),
                "subtotal": {"type": "number", "minimum": 0},
                "tax_amount": {"type": "number", "minimum": 0, "default": 0},
                "tip_amount": {"type": "number", "minimum": 0, "default": 0},
                "total_amount": {"type": "number", "minimum": 0},
                "currency": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 3,
                    "default": "USD",
                },
                "notes": {"type": ["string", "null"]},
                "confidence_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1.0,
                },
            },
            "required": [
                "vendor_name",
                "transaction_date",
                "subtotal",
                "total_amount",
            ],
        }
