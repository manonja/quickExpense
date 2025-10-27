"""Tax calculator agent for GST/HST validation and deductible amount calculations."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import autogen

from quickexpense.services.llm_provider import LLMProviderFactory
from quickexpense.services.rate_limiter import RateLimiter

from .base import BaseReceiptAgent

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)

# Constants
TAX_DISCREPANCY_PASS_THRESHOLD = 5  # 5% or less is considered pass
TAX_DISCREPANCY_WARNING_THRESHOLD = 15  # 5-15% is warning
TOTAL_VALIDATION_TOLERANCE = 0.02  # 2 cent tolerance
HIGH_TAX_RATE_THRESHOLD = 20  # 20% or higher is unusually high
LOW_TAX_RATE_THRESHOLD = 3  # 3% or lower is unusually low
CONFIDENCE_HIGH_DISCREPANCY_THRESHOLD = 2  # 2% or less gets confidence boost
CONFIDENCE_LOW_DISCREPANCY_THRESHOLD = 10  # 10% or more gets confidence reduction


class TaxCalculatorAgent(BaseReceiptAgent):
    """Agent specialized in tax calculations, GST/HST validation, and deductibles."""

    def __init__(
        self,
        settings: Settings,
        name: str = "TaxCalculatorAgent",
        timeout_seconds: float = 2.0,
    ) -> None:
        """Initialize the tax calculator agent.

        Args:
            settings: Application settings with Gemini configuration
            name: Agent name
            timeout_seconds: Processing timeout
        """
        super().__init__(name, timeout_seconds)
        self.settings = settings

        # Canadian provincial tax rates (as of 2025)
        self.provincial_tax_rates = {
            "AB": {"gst": 5.0, "pst": 0.0, "hst": 0.0},  # Alberta
            "BC": {"gst": 5.0, "pst": 7.0, "hst": 0.0},  # British Columbia
            "MB": {"gst": 5.0, "pst": 7.0, "hst": 0.0},  # Manitoba
            "NB": {"gst": 0.0, "pst": 0.0, "hst": 15.0},  # New Brunswick
            "NL": {"gst": 0.0, "pst": 0.0, "hst": 15.0},  # Newfoundland and Labrador
            "NT": {"gst": 5.0, "pst": 0.0, "hst": 0.0},  # Northwest Territories
            "NS": {"gst": 0.0, "pst": 0.0, "hst": 15.0},  # Nova Scotia
            "NU": {"gst": 5.0, "pst": 0.0, "hst": 0.0},  # Nunavut
            "ON": {"gst": 0.0, "pst": 0.0, "hst": 13.0},  # Ontario
            "PE": {"gst": 0.0, "pst": 0.0, "hst": 15.0},  # Prince Edward Island
            "QC": {"gst": 5.0, "pst": 9.975, "hst": 0.0},  # Quebec
            "SK": {"gst": 5.0, "pst": 6.0, "hst": 0.0},  # Saskatchewan
            "YT": {"gst": 5.0, "pst": 0.0, "hst": 0.0},  # Yukon
        }

        # Configure LLM provider
        self.llm_provider = LLMProviderFactory.create(settings)
        self.llm_config = self.llm_provider.get_autogen_config()
        # Override temperature for mathematical accuracy
        self.llm_config["config_list"][0]["temperature"] = 0.05
        self.llm_config["config_list"][0]["max_tokens"] = 2048

        # Initialize rate limiter for TogetherAI if that's the provider
        if self.llm_provider.provider_name == "together":
            self.rate_limiter = RateLimiter.get_instance("together", settings)

        # Create the autogen assistant agent
        self.agent = autogen.AssistantAgent(
            name="tax_calculator_specialist",
            llm_config=self.llm_config,
            system_message=self._get_tax_system_message(),
        )

    async def _process_internal(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate and validate tax amounts and deductible portions.

        Args:
            receipt_data: Extracted receipt data
            context: Processing context (including CRA categorization)

        Returns:
            Dictionary with tax calculation results
        """
        # Extract key information
        subtotal = float(receipt_data.get("subtotal", 0))
        tax_amount = float(receipt_data.get("tax_amount", 0))
        total_amount = float(receipt_data.get("total_amount", 0))
        vendor_location = self._determine_vendor_location(receipt_data)

        # Get CRA categorization from context
        cra_data = context.get("cra_categorization", {})
        deductibility_percentage = cra_data.get("deductibility_percentage", 100)
        category = cra_data.get("category", "General Business Expense")

        # Prepare tax calculation request
        calculation_request = {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "vendor_location": vendor_location,
            "deductibility_percentage": deductibility_percentage,
            "expense_category": category,
        }

        # Use autogen agent to perform tax calculations and validation
        calculation_result = await self._calculate_taxes_with_agent(calculation_request)

        # Add our own validation and calculations
        return self._validate_tax_calculations(calculation_result, calculation_request)

    async def _calculate_taxes_with_agent(
        self, calculation_request: dict[str, Any]
    ) -> dict[str, Any]:
        """Use autogen agent to calculate and validate taxes.

        Args:
            calculation_request: Tax calculation parameters

        Returns:
            Tax calculation results
        """
        prompt = self._build_tax_calculation_prompt(calculation_request)

        user_proxy = autogen.UserProxyAgent(
            name="user",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )

        try:
            # Check rate limit before agent call
            self.check_rate_limit()

            response = await user_proxy.a_initiate_chat(
                self.agent,
                message=prompt,
                max_turns=1,
            )

            last_message = response.chat_history[-1]["content"]

            try:
                calculation_data = json.loads(last_message)
            except json.JSONDecodeError:
                import re

                json_match = re.search(r"\{.*\}", last_message, re.DOTALL)
                if json_match:
                    calculation_data = json.loads(json_match.group())
                else:
                    # Fall back to manual calculation
                    calculation_data = self._manual_tax_calculation(calculation_request)

            self._validate_calculation_result(calculation_data)
            return calculation_data  # type: ignore[no-any-return]

        except Exception as e:  # noqa: BLE001 # Fallback to manual calculation
            self.logger.warning(
                "Agent tax calculation failed, using manual: %s", e, exc_info=True
            )
            return self._manual_tax_calculation(calculation_request)

    def _build_tax_calculation_prompt(self, request: dict[str, Any]) -> str:
        """Build the tax calculation prompt for the agent."""
        subtotal = request["subtotal"]
        tax_amount = request["tax_amount"]
        total_amount = request["total_amount"]
        vendor_location = request["vendor_location"]
        deductibility_percentage = request["deductibility_percentage"]
        category = request["expense_category"]

        # Get applicable tax rates for the location
        tax_rates = self.provincial_tax_rates.get(
            vendor_location, self.provincial_tax_rates["ON"]
        )

        return f"""
Analyze and validate the tax calculations for this Canadian business expense:

EXPENSE DETAILS:
- Subtotal: ${subtotal:.2f}
- Tax Amount (from receipt): ${tax_amount:.2f}
- Total Amount: ${total_amount:.2f}
- Vendor Location: {vendor_location}
- Expense Category: {category}
- Deductibility Rate: {deductibility_percentage}%

APPLICABLE TAX RATES FOR {vendor_location}:
- GST: {tax_rates['gst']}%
- PST: {tax_rates['pst']}%
- HST: {tax_rates['hst']}%

VALIDATION TASKS:
1. Verify mathematical accuracy: subtotal + tax = total
2. Calculate expected tax based on location rates
3. Identify any tax discrepancies
4. Calculate the deductible business portion
5. Determine GST/HST Input Tax Credit eligibility
6. Flag any unusual tax situations

SPECIAL CONSIDERATIONS:
- Some items may be tax-exempt (e.g., certain food items)
- Tips are not subject to GST/HST
- International transactions may have different rules
- Some services may have different tax treatments

Return your analysis as JSON:
{{
    "calculated_gst_hst": "number (expected GST/HST amount)",
    "calculated_pst": "number (expected PST amount if applicable)",
    "total_calculated_tax": "number (total expected tax)",
    "tax_discrepancy": "number (difference between receipt and calculated)",
    "tax_discrepancy_percentage": "number (discrepancy as % of calculated)",
    "deductible_amount": "number (business deductible portion)",
    "deductible_tax_amount": "number (deductible tax portion)",
    "input_tax_credit_eligible": "boolean (GST/HST ITC eligibility)",
    "validation_result": "PASS|WARNING|FAIL",
    "validation_notes": "string (explanation of any issues)",
    "tax_breakdown": {{
        "taxable_subtotal": "number",
        "tax_exempt_amount": "number (if any)",
        "gst_hst_rate_used": "number",
        "pst_rate_used": "number"
    }},
    "confidence_score": "number (0-1, confidence in calculations)"
}}

Return ONLY the JSON object.
"""

    def _manual_tax_calculation(self, request: dict[str, Any]) -> dict[str, Any]:
        """Perform manual tax calculation as fallback.

        Args:
            request: Tax calculation parameters

        Returns:
            Manual tax calculation results
        """
        subtotal = request["subtotal"]
        tax_amount = request["tax_amount"]
        total_amount = request["total_amount"]
        vendor_location = request["vendor_location"]
        deductibility_percentage = request["deductibility_percentage"]

        # Get tax rates for location
        rates = self.provincial_tax_rates.get(
            vendor_location, self.provincial_tax_rates["ON"]
        )

        # Calculate expected taxes
        if rates["hst"] > 0:
            # HST province
            calculated_tax = subtotal * (rates["hst"] / 100)
            gst_hst = calculated_tax
            pst = 0.0
        else:
            # GST + PST province
            gst_hst = subtotal * (rates["gst"] / 100)
            pst = subtotal * (rates["pst"] / 100)
            calculated_tax = gst_hst + pst

        # Calculate discrepancy
        tax_discrepancy = abs(tax_amount - calculated_tax)
        discrepancy_percentage = (tax_discrepancy / max(calculated_tax, 0.01)) * 100

        # Calculate deductible amounts
        deductible_amount = (subtotal * deductibility_percentage) / 100
        deductible_tax_amount = (tax_amount * deductibility_percentage) / 100

        # Determine validation result
        if discrepancy_percentage <= TAX_DISCREPANCY_PASS_THRESHOLD:
            validation_result = "PASS"
            validation_notes = "Tax calculation within acceptable range"
        elif discrepancy_percentage <= TAX_DISCREPANCY_WARNING_THRESHOLD:
            validation_result = "WARNING"
            validation_notes = (
                f"Tax discrepancy of {discrepancy_percentage:.1f}% detected"
            )
        else:
            validation_result = "FAIL"
            validation_notes = (
                f"Significant tax discrepancy of {discrepancy_percentage:.1f}%"
            )

        # Check mathematical consistency
        calculated_total = subtotal + tax_amount
        if abs(calculated_total - total_amount) > TOTAL_VALIDATION_TOLERANCE:
            validation_result = "FAIL"
            validation_notes += "; Total amount doesn't match subtotal + tax"

        return {
            "calculated_gst_hst": round(gst_hst, 2),
            "calculated_pst": round(pst, 2),
            "total_calculated_tax": round(calculated_tax, 2),
            "tax_discrepancy": round(tax_discrepancy, 2),
            "tax_discrepancy_percentage": round(discrepancy_percentage, 1),
            "deductible_amount": round(deductible_amount, 2),
            "deductible_tax_amount": round(deductible_tax_amount, 2),
            "input_tax_credit_eligible": gst_hst > 0 and deductibility_percentage > 0,
            "validation_result": validation_result,
            "validation_notes": validation_notes,
            "tax_breakdown": {
                "taxable_subtotal": round(subtotal, 2),
                "tax_exempt_amount": 0.0,
                "gst_hst_rate_used": rates["hst"] if rates["hst"] > 0 else rates["gst"],
                "pst_rate_used": rates["pst"],
            },
            "confidence_score": 0.85 if validation_result == "PASS" else 0.65,
        }

    def _determine_vendor_location(self, receipt_data: dict[str, Any]) -> str:
        """Determine vendor province/territory from receipt data.

        Args:
            receipt_data: Extracted receipt data

        Returns:
            Two-letter province/territory code
        """
        vendor_address = receipt_data.get("vendor_address", "").upper()

        # Simple province detection based on address
        province_indicators = {
            "ON": ["ONTARIO", "ONT", " ON ", "ON,"],
            "BC": ["BRITISH COLUMBIA", "BC", " BC ", "BC,"],
            "AB": ["ALBERTA", "AB", " AB ", "AB,"],
            "QC": ["QUEBEC", "QUE", " QC ", "QC,", "QUÉBEC"],
            "NS": ["NOVA SCOTIA", "NS", " NS ", "NS,"],
            "NB": ["NEW BRUNSWICK", "NB", " NB ", "NB,"],
            "MB": ["MANITOBA", "MB", " MB ", "MB,"],
            "SK": ["SASKATCHEWAN", "SK", " SK ", "SK,"],
            "PE": ["PRINCE EDWARD ISLAND", "PEI", "PE", " PE ", "PE,"],
            "NL": ["NEWFOUNDLAND", "NL", " NL ", "NL,"],
            "YT": ["YUKON", "YT", " YT ", "YT,"],
            "NT": ["NORTHWEST TERRITORIES", "NT", " NT ", "NT,"],
            "NU": ["NUNAVUT", "NU", " NU ", "NU,"],
        }

        for province, indicators in province_indicators.items():
            for indicator in indicators:
                if indicator in vendor_address:
                    return province

        # Default to Ontario if no province detected
        return "ON"

    def _validate_tax_calculations(
        self,
        calculation_result: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and enhance the tax calculation results.

        Args:
            calculation_result: Results from agent calculation
            request: Original calculation request

        Returns:
            Enhanced calculation results
        """
        # Add our own validation logic
        validation_flags = []

        # Check for reasonable tax rates
        subtotal = request["subtotal"]
        calculated_tax = calculation_result.get("total_calculated_tax", 0)
        if subtotal > 0:
            effective_rate = (calculated_tax / subtotal) * 100
            if effective_rate > HIGH_TAX_RATE_THRESHOLD:  # Very high tax rate
                validation_flags.append("Unusually high effective tax rate")
            elif effective_rate < LOW_TAX_RATE_THRESHOLD:  # Very low tax rate
                validation_flags.append("Unusually low effective tax rate")

        # Check deductible amount reasonableness
        deductible_amount = calculation_result.get("deductible_amount", 0)
        total_amount = request["total_amount"]
        if deductible_amount > total_amount:
            validation_flags.append("Deductible amount exceeds total amount")

        # Add validation flags to result
        if validation_flags:
            existing_notes = calculation_result.get("validation_notes", "")
            calculation_result["validation_notes"] = (
                f"{existing_notes}; {'; '.join(validation_flags)}"
            )

        # Add additional metadata
        calculation_result["calculation_metadata"] = {
            "vendor_location": request["vendor_location"],
            "deductibility_percentage": request["deductibility_percentage"],
            "expense_category": request["expense_category"],
            "validation_flags": validation_flags,
        }

        return calculation_result

    def _validate_calculation_result(self, data: dict[str, Any]) -> None:
        """Validate the calculation result structure.

        Args:
            data: Calculation result to validate

        Raises:
            ValueError: If data is invalid
        """
        required_fields = [
            "calculated_gst_hst",
            "deductible_amount",
            "validation_result",
        ]

        for field in required_fields:
            if field not in data:
                msg = f"Missing required field in tax calculation: {field}"
                raise ValueError(msg)

        # Validate validation result
        validation_result = data.get("validation_result")
        if validation_result not in ["PASS", "WARNING", "FAIL"]:
            msg = f"Invalid validation result: {validation_result}"
            raise ValueError(msg)

    def _calculate_confidence(
        self,
        result_data: dict[str, Any],
        receipt_data: dict[str, Any],
    ) -> float:
        """Calculate confidence score for the tax calculations.

        Args:
            result_data: Tax calculation results
            receipt_data: Original receipt data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with agent's confidence if available
        base_confidence = result_data.get("confidence_score", 0.75)

        # Adjust based on validation result
        validation_result = result_data.get("validation_result", "WARNING")
        if validation_result == "PASS":
            base_confidence += 0.1
        elif validation_result == "WARNING":
            base_confidence -= 0.05
        elif validation_result == "FAIL":
            base_confidence -= 0.2

        # Adjust based on tax discrepancy
        discrepancy_percentage = result_data.get("tax_discrepancy_percentage", 0)
        if discrepancy_percentage <= CONFIDENCE_HIGH_DISCREPANCY_THRESHOLD:
            base_confidence += 0.05
        elif discrepancy_percentage >= CONFIDENCE_LOW_DISCREPANCY_THRESHOLD:
            base_confidence -= 0.1

        # Adjust based on mathematical consistency
        try:
            subtotal = float(receipt_data.get("subtotal", 0))
            tax_amount = float(receipt_data.get("tax_amount", 0))
            total_amount = float(receipt_data.get("total_amount", 0))

            if (
                abs((subtotal + tax_amount) - total_amount)
                <= TOTAL_VALIDATION_TOLERANCE
            ):
                base_confidence += 0.05
        except (ValueError, TypeError):
            base_confidence -= 0.05

        return max(0.0, min(base_confidence, 1.0))  # type: ignore[no-any-return]

    def _get_tax_system_message(self) -> str:
        """Get the system message for the tax calculator agent."""
        return """
You are a Canadian tax calculation specialist with expertise in:

1. GST/HST rates across all provinces and territories
2. Provincial Sales Tax (PST) calculations
3. Input Tax Credit (ITC) eligibility rules
4. Business expense deductibility calculations
5. Tax validation and discrepancy detection

Key responsibilities:
- Verify mathematical accuracy of tax calculations
- Calculate expected taxes based on location and rates
- Determine deductible business portions
- Identify tax discrepancies and unusual situations
- Assess ITC eligibility for GST/HST

You must be precise with calculations and conservative with validation.
Always flag significant discrepancies for manual review.
"""

    def _get_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Get metadata about the tax calculation process."""
        metadata = super()._get_metadata(result_data)
        metadata.update(
            {
                "validation_result": result_data.get("validation_result"),
                "tax_discrepancy_percentage": result_data.get(
                    "tax_discrepancy_percentage"
                ),
                "input_tax_credit_eligible": result_data.get(
                    "input_tax_credit_eligible"
                ),
                "calculation_method": "agent_assisted",
            }
        )
        return metadata
