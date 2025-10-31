"""CRA Rules agent for applying Canadian tax law and categorization."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import autogen

from quickexpense.services.cra_business_rules import CRABusinessRulesService
from quickexpense.services.llm_provider import LLMProviderFactory
from quickexpense.services.rate_limiter import RateLimiter

from .base import BaseReceiptAgent

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)

# Allowed expense categories for CRA compliance
ALLOWED_CATEGORIES = [
    "Travel-Lodging",
    "Travel-Meals",
    "Travel-Taxes",
    "Office-Supplies",
    "Fuel-Vehicle",
    "Capital-Equipment",
    "Tax-GST/HST",
    "Professional-Services",
    "Meals & Entertainment",
    "Uncategorized-Review-Required",
]


class CRArulesAgent(BaseReceiptAgent):
    """Agent specialized in applying CRA business rules and tax categorization."""

    def __init__(
        self,
        settings: Settings,
        name: str = "CRArulesAgent",
        timeout_seconds: float = 2.0,
        rules_csv_path: str | None = None,
    ) -> None:
        """Initialize the CRA rules agent.

        Args:
            settings: Application settings with Gemini configuration
            name: Agent name
            timeout_seconds: Processing timeout
            rules_csv_path: Optional path to CRA rules CSV file
        """
        super().__init__(name, timeout_seconds)
        self.settings = settings
        self.cra_rules_service = CRABusinessRulesService(rules_csv_path)

        # Phase 2: Store RAG results for programmatic citation injection
        self._last_rag_results: list[Any] = []

        # Configure LLM provider - FORCE GEMINI for better citation extraction
        # Phase 1 of RAG Citation Fix: Switch to Gemini for improved
        # instruction-following
        self.llm_provider = LLMProviderFactory.create(
            settings, provider_override="gemini"
        )
        self.llm_config = self.llm_provider.get_autogen_config()
        # Override temperature for consistent categorization
        self.llm_config["config_list"][0]["temperature"] = 0.1
        self.llm_config["config_list"][0]["max_tokens"] = 2048

        # Initialize rate limiter for TogetherAI if that's the provider
        if self.llm_provider.provider_name == "together":
            self.rate_limiter = RateLimiter.get_instance("together", settings)

        # Create the autogen assistant agent
        self.agent = autogen.AssistantAgent(
            name="cra_rules_specialist",
            llm_config=self.llm_config,
            system_message=self._get_cra_system_message(),
        )

    async def _process_internal(
        self,
        receipt_data: dict[str, Any],
        context: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Apply CRA rules to categorize the expense.

        Args:
            receipt_data: Extracted receipt data
            context: Processing context

        Returns:
            Dictionary with CRA categorization results
        """
        vendor_name = receipt_data.get("vendor_name", "")
        line_items = receipt_data.get("line_items", [])
        total_amount = receipt_data.get("total_amount", 0)

        # Defensive: Handle empty line items
        if not line_items:
            logger.warning("No line items to process")
            return {
                "processed_items": [],
                "warning": "No line items found in receipt data",
                "confidence": 0.0,
            }

        # Extract line item descriptions
        line_item_descriptions = [
            item.get("description", "") for item in line_items if isinstance(item, dict)
        ]

        # Find matching rules using the CRA rules service
        rule_matches = self.cra_rules_service.find_matching_rules(
            vendor_name=vendor_name,
            line_item_descriptions=line_item_descriptions,
            amount=total_amount,
        )

        # If we have rule matches, use the best one
        if rule_matches:
            best_match = rule_matches[0]

            # Use autogen to validate and potentially refine the categorization
            return await self._refine_categorization_with_agent(
                receipt_data, best_match, rule_matches
            )
        # Use autogen to make a categorization decision when no rules match
        return await self._categorize_with_agent_fallback(receipt_data)

    async def _refine_categorization_with_agent(
        self,
        receipt_data: dict[str, Any],
        best_match: Any,  # RuleMatchResult  # noqa: ANN401
        all_matches: list[Any],
    ) -> dict[str, Any]:
        """Use autogen to validate and refine the rule-based categorization.

        Args:
            receipt_data: Extracted receipt data
            best_match: Best matching rule result
            all_matches: All matching rule results

        Returns:
            Refined categorization result
        """
        # Prepare the prompt for the CRA agent
        prompt = self._build_refinement_prompt(receipt_data, best_match, all_matches)

        # Create a user proxy for the interaction
        user_proxy = autogen.UserProxyAgent(
            name="user",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )

        try:
            # Check rate limit before agent call
            self.check_rate_limit()

            # Have the agent analyze and potentially refine the categorization
            response = await user_proxy.a_initiate_chat(
                self.agent,
                message=prompt,
                max_turns=1,
            )

            # Extract and parse the JSON response with tax calculations
            last_message = response.chat_history[-1]["content"]
            line_items = receipt_data.get("line_items", [])
            refined_data = self._parse_response(
                last_message, input_line_items=line_items
            )

            # Phase 2: Programmatically inject citations (guaranteed 100%)
            self._inject_citations_programmatically(
                refined_data.get("processed_items", [])
            )

            # If parsing failed or no items, fall back to rule-based result
            if not refined_data.get("processed_items"):
                logger.warning(
                    "No processed items in agent response, using rule-based result"
                )
                refined_data = self._rule_match_to_dict(best_match)

            return refined_data

        except Exception as e:  # noqa: BLE001
            self.logger.warning(
                "Agent refinement failed, using rule-based result: %s", e
            )
            return self._rule_match_to_dict(best_match)

    async def _categorize_with_agent_fallback(
        self,
        receipt_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Use autogen to categorize when no rules match.

        Args:
            receipt_data: Extracted receipt data

        Returns:
            Agent-generated categorization result
        """
        prompt = self._build_fallback_prompt(receipt_data)

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
            line_items = receipt_data.get("line_items", [])
            categorization_data = self._parse_response(
                last_message, input_line_items=line_items
            )

            # Phase 2: Programmatically inject citations (guaranteed 100%)
            self._inject_citations_programmatically(
                categorization_data.get("processed_items", [])
            )

            # If parsing failed or no items, use fallback rule
            if not categorization_data.get("processed_items"):
                logger.warning(
                    "No processed items in agent response, using fallback rule"
                )
                fallback_rule = self.cra_rules_service.get_fallback_rule()
                return self._rule_match_to_dict(fallback_rule)

            return categorization_data

        except Exception as e:  # noqa: BLE001
            # Return fallback categorization on error
            self.logger.error("Error in categorization: %s", str(e))
            fallback_rule = self.cra_rules_service.get_fallback_rule()
            return self._rule_match_to_dict(fallback_rule)

    def _add_tax_and_tip_items(
        self, line_items: list[dict[str, Any]], receipt_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Add tax/tip as line items if present and not already included.

        This helper normalizes receipt data by ensuring GST/HST and tips from
        top-level fields are included in the line_items array for processing.

        Args:
            line_items: Original line items from receipt
            receipt_data: Full receipt data with tax_amount and tip_amount

        Returns:
            Enhanced line items list with tax/tip added if applicable
        """
        items = line_items.copy()  # Defensive: don't mutate input

        # Add GST/HST if present in top-level field
        tax_amount = receipt_data.get("tax_amount", 0)
        # Convert to float if string (defensive)
        try:
            tax_amount = float(tax_amount) if tax_amount else 0.0
        except (ValueError, TypeError):
            tax_amount = 0.0

        if tax_amount and tax_amount > 0:
            # Check if not already in items (case-insensitive)
            has_tax = any(
                "gst" in str(item.get("description", "")).lower()
                or "hst" in str(item.get("description", "")).lower()
                or "tax" in str(item.get("description", "")).lower()
                for item in items
            )
            if not has_tax:
                items.append(
                    {
                        "description": "GST/HST",
                        "total_price": float(tax_amount),
                        "quantity": 1,
                        "unit_price": float(tax_amount),
                    }
                )
                logger.debug(
                    "Added GST/HST line item from top-level tax_amount: $%.2f",
                    float(tax_amount),
                )

        # Add tip if present in top-level field
        tip_amount = receipt_data.get("tip_amount", 0)
        # Convert to float if string (defensive)
        try:
            tip_amount = float(tip_amount) if tip_amount else 0.0
        except (ValueError, TypeError):
            tip_amount = 0.0

        if tip_amount and tip_amount > 0:
            has_tip = any(
                "tip" in str(item.get("description", "")).lower() for item in items
            )
            if not has_tip:
                items.append(
                    {
                        "description": "Tip",
                        "total_price": float(tip_amount),
                        "quantity": 1,
                        "unit_price": float(tip_amount),
                    }
                )
                logger.debug(
                    "Added Tip line item from top-level tip_amount: $%.2f",
                    float(tip_amount),
                )

        return items

    def _build_refinement_prompt(
        self,
        receipt_data: dict[str, Any],
        best_match: Any,  # noqa: ANN401
        all_matches: list[Any],  # noqa: ARG002
    ) -> str:
        """Build prompt with RAG context for refining categorization."""
        vendor_name = receipt_data.get("vendor_name", "")
        line_items = receipt_data.get("line_items", [])

        # Add tax/tip items from top-level fields before processing
        line_items = self._add_tax_and_tip_items(line_items, receipt_data)

        # GET RAG CONTEXT (NEW)
        line_items_text = " ".join(
            [
                item.get("description", "")
                for item in line_items
                if isinstance(item, dict)
            ]
        )
        rag_context = self._get_rag_context(
            expense_description=line_items_text,
            expense_category=best_match.rule.category,
            vendor_name=vendor_name,
        )

        # Build structured JSON input array (NOT concatenated string)
        line_items_json = json.dumps(
            [
                {
                    "line_number": i + 1,
                    "description": item.get("description", ""),
                    "amount": float(item.get("total_price", 0)),
                }
                for i, item in enumerate(line_items)
                if isinstance(item, dict)
            ]
        )

        return f"""
You are an expert Canadian tax categorization agent for business expenses.

**AUTHORITATIVE CRA CONTEXT:**
---
{rag_context}
---

**CRITICAL INSTRUCTIONS:**
1. You MUST process EACH line item separately - do NOT aggregate or summarize
2. You MUST return valid JSON with a "processed_items" array
3. You MUST only use categories from the ALLOWED_CATEGORIES list below
4. If an item's business purpose is ambiguous or possibly personal, use
   "Uncategorized-Review-Required"
5. Apply CRA rules: Meals 50%, Lodging 100%, GST/HST 100%, Office Supplies 100%

**ALLOWED_CATEGORIES:**
{json.dumps(ALLOWED_CATEGORIES, indent=2)}

**REQUIRED OUTPUT SCHEMA:**
{{
  "processed_items": [
    {{
      "line_number": integer,
      "original_description": "string",
      "category": "string (from ALLOWED_CATEGORIES)",
      "deductibility_percent": integer (0-100),
      "reasoning": "Brief explanation referencing CRA rules if applicable",
      "citations": []
    }}
  ]
}}

**SUGGESTED CATEGORIZATION (from rules engine):**
- Category: {best_match.rule.category}
- Deductibility: {best_match.rule.deductibility_rate}%
- Confidence: {best_match.confidence_score:.2f}
- Reasoning: {best_match.matching_reason}

**EXPENSE TO PROCESS:**
INPUT:
{{
  "vendor_name": "{vendor_name}",
  "line_items": {line_items_json}
}}

YOUR RESPONSE (valid JSON only):
"""

    def _build_fallback_prompt(self, receipt_data: dict[str, Any]) -> str:
        """Build prompt with RAG context for fallback categorization."""
        logger.info("🔍 Using FALLBACK prompt path (no business rules match)")
        vendor_name = receipt_data.get("vendor_name", "")
        line_items = receipt_data.get("line_items", [])

        # Add tax/tip items from top-level fields before processing
        line_items = self._add_tax_and_tip_items(line_items, receipt_data)

        # GET RAG CONTEXT (NEW)
        line_items_text = " ".join(
            [
                item.get("description", "")
                for item in line_items
                if isinstance(item, dict)
            ]
        )
        rag_context = self._get_rag_context(
            expense_description=line_items_text,
            expense_category=None,  # No category hint in fallback
            vendor_name=vendor_name,
        )

        # Build structured JSON input array (NOT concatenated string)
        line_items_json = json.dumps(
            [
                {
                    "line_number": i + 1,
                    "description": item.get("description", ""),
                    "amount": float(item.get("total_price", 0)),
                }
                for i, item in enumerate(line_items)
                if isinstance(item, dict)
            ]
        )

        return f"""
You are an expert Canadian tax categorization agent for business expenses.

**AUTHORITATIVE CRA CONTEXT:**
---
{rag_context}
---

**CRITICAL INSTRUCTIONS:**
1. You MUST process EACH line item separately - do NOT aggregate or summarize
2. You MUST return valid JSON with a "processed_items" array
3. You MUST only use categories from the ALLOWED_CATEGORIES list below
4. If an item's business purpose is ambiguous or possibly personal, use
   "Uncategorized-Review-Required"
5. Apply CRA rules: Meals 50%, Lodging 100%, GST/HST 100%, Office Supplies 100%

**ALLOWED_CATEGORIES:**
{json.dumps(ALLOWED_CATEGORIES, indent=2)}

**REQUIRED OUTPUT SCHEMA:**
{{
  "processed_items": [
    {{
      "line_number": integer,
      "original_description": "string",
      "category": "string (from ALLOWED_CATEGORIES)",
      "deductibility_percent": integer (0-100),
      "reasoning": "Brief explanation referencing CRA rules if applicable",
      "citations": []
    }}
  ]
}}

**KEY CRA RULES:**
- Meals & Entertainment: 50% deductible (ITA Section 67.1)
- Travel Lodging: 100% deductible
- GST/HST: 100% deductible as Input Tax Credit
- Office Supplies: 100% deductible
- Professional Services: 100% deductible

**EXPENSE TO PROCESS:**
INPUT:
{{
  "vendor_name": "{vendor_name}",
  "line_items": {line_items_json}
}}

YOUR RESPONSE (valid JSON only):
"""

    def _parse_response(
        self, llm_response: str, input_line_items: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Parse LLM response with validation, error handling, and tax calculations.

        Args:
            llm_response: Raw LLM response string
            input_line_items: Optional list of original line items for amount lookup

        Returns:
            Parsed and validated response dictionary with calculated amounts
        """
        try:
            # Remove markdown code blocks if present
            cleaned = llm_response.strip()
            cleaned = cleaned.removeprefix("```json")
            cleaned = cleaned.removeprefix("```")
            cleaned = cleaned.removesuffix("```")
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)

            # Validate structure
            if "processed_items" not in parsed:
                logger.error("Missing 'processed_items' key in LLM response")
                msg = "Invalid response structure"
                raise ValueError(msg)

            # Validate and sanitize categories, initialize citations
            for item in parsed["processed_items"]:
                category = item.get("category", "")
                if category not in ALLOWED_CATEGORIES:
                    logger.warning(
                        "Invalid category '%s' for line %s, replacing with '%s'",
                        category,
                        item.get("line_number"),
                        "Uncategorized-Review-Required",
                    )
                    item["category"] = "Uncategorized-Review-Required"
                    item["deductibility_percent"] = 0
                    item["reasoning"] = (
                        f"Original category '{category}' not recognized. "
                        "Manual review required."
                    )

                # Initialize citations field if missing (NEW)
                if "citations" not in item:
                    item["citations"] = []

            # Add tax calculations if line items provided
            if input_line_items:
                # Create amount lookup map (line_number → original amount)
                amount_map = {}
                for i, item in enumerate(input_line_items):
                    line_num = i + 1
                    # Extract amount, handling dict types
                    # NOTE: DataExtractionAgent uses "amount" field (not "total_price")
                    amount = float(item.get("amount", 0))
                    amount_map[line_num] = amount

                # Add calculated fields to each processed item
                for item in parsed["processed_items"]:
                    line_num = item.get("line_number")

                    # Defensive: Use .get() with defaults to prevent KeyError
                    original_amount = amount_map.get(line_num, 0.0)
                    deductibility = item.get("deductibility_percent", 0)

                    # Add calculated fields
                    item["original_amount"] = round(original_amount, 2)
                    item["deductible_amount"] = round(
                        (original_amount * deductibility) / 100.0, 2
                    )

            return parsed  # type: ignore[no-any-return]

        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s\nResponse: %s", e, llm_response[:200])
            return {
                "processed_items": [],
                "error": "Failed to parse LLM response as JSON",
                "raw_response": llm_response[:500],
            }
        except Exception as e:  # noqa: BLE001
            logger.error("Unexpected error parsing response: %s", e)
            return {
                "processed_items": [],
                "error": str(e),
            }

    def _format_alternative_matches(self, matches: list[Any]) -> str:
        """Format alternative rule matches for display."""
        if not matches:
            return "None"

        formatted = [
            (
                f"- {match.rule.category} ({match.confidence_score:.2f}): "
                f"{match.rule.description}"
            )
            for match in matches[:4]  # Limit to 4 alternatives
        ]
        return "\n".join(formatted)

    def _rule_match_to_dict(self, rule_match: Any) -> dict[str, Any]:  # noqa: ANN401
        """Convert a RuleMatchResult to a dictionary."""
        return {
            "category": rule_match.rule.category,
            "deductibility_percentage": rule_match.rule.deductibility_rate,
            "qb_account": f"{rule_match.rule.category} Account",  # Simplified for now
            "tax_treatment": "standard",  # Would be enhanced based on rule
            "ita_section": rule_match.rule.ita_section,
            "audit_risk": rule_match.rule.audit_risk,
            "t2125_line": rule_match.rule.t2125_line,
            "rule_applied": (
                f"CSV Rule: "
                f"{getattr(rule_match.rule, 'id', rule_match.rule.description)}"
            ),
            "confidence_adjustment": 0.0,
            "reasoning": rule_match.matching_reason,
            "matched_keywords": rule_match.matched_keywords,
        }

    def _validate_categorization_result(self, data: dict[str, Any]) -> None:
        """Validate the categorization result.

        Args:
            data: Categorization result to validate

        Raises:
            ValueError: If data is invalid
        """
        required_fields = [
            "category",
            "deductibility_percentage",
            "audit_risk",
            "rule_applied",
        ]

        for field in required_fields:
            if field not in data:
                msg = f"Missing required field in categorization: {field}"
                raise ValueError(msg)

        # Validate deductibility percentage
        deductibility = data.get("deductibility_percentage")
        try:
            deductibility_val = (
                float(deductibility) if deductibility is not None else 0.0
            )
            if not 0 <= deductibility_val <= 100:  # noqa: PLR2004
                msg = f"Deductibility percentage must be 0-100, got {deductibility_val}"
                raise ValueError(msg)
        except (ValueError, TypeError) as e:
            msg = f"Invalid deductibility percentage: {deductibility}"
            raise ValueError(msg) from e

        # Validate audit risk
        audit_risk = data.get("audit_risk")
        if audit_risk not in ["LOW", "MEDIUM", "HIGH"]:
            msg = f"Audit risk must be LOW, MEDIUM, or HIGH, got {audit_risk}"
            raise ValueError(msg)

    def _calculate_confidence(
        self,
        result_data: dict[str, Any],
        receipt_data: dict[str, Any],  # noqa: ARG002
    ) -> float:
        """Calculate confidence score for the categorization.

        Args:
            result_data: Categorization results
            receipt_data: Original receipt data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.7  # Base confidence for CRA categorization

        # Adjust based on rule application method
        rule_applied = result_data.get("rule_applied", "")
        if "CSV Rule" in rule_applied:
            base_confidence += 0.15  # Rule-based categorization is more confident
        elif "Agent analysis" in rule_applied:
            base_confidence += 0.05  # Agent-based is less confident but still good

        # Adjust based on confidence adjustment from the agent
        confidence_adjustment = result_data.get("confidence_adjustment", 0.0)
        try:
            adjustment = float(confidence_adjustment)
            base_confidence += adjustment
        except (ValueError, TypeError):
            pass

        # Adjust based on audit risk
        audit_risk = result_data.get("audit_risk", "MEDIUM")
        if audit_risk == "LOW":
            base_confidence += 0.05
        elif audit_risk == "HIGH":
            base_confidence -= 0.1

        # Adjust based on matched keywords
        matched_keywords = result_data.get("matched_keywords", [])
        if isinstance(matched_keywords, list) and len(matched_keywords) > 0:
            base_confidence += min(len(matched_keywords) * 0.02, 0.1)

        return max(0.0, min(base_confidence, 1.0))

    def _get_rag_context(
        self,
        expense_description: str,
        expense_category: str | None = None,
        vendor_name: str | None = None,
    ) -> str:
        """Retrieve and format CRA context from RAG database.

        Args:
            expense_description: Line items or description
            expense_category: Category hint (e.g., "meals", "travel")
            vendor_name: Vendor name for context

        Returns:
            Formatted context string for LLM prompt
        """
        # Mapping from application categories to simpler RAG-friendly terms
        # Note: RAG database has limited expense_types indexed (mainly "meals")
        # For other categories, we rely on keyword search in query without filter
        rag_category_map = {
            "Travel-Lodging": "hotel travel accommodation",
            "Travel-Meals": "meals",
            "Meals & Entertainment": "meals",
            "Fuel-Vehicle": "vehicle fuel",
            "Office-Supplies": "office supplies",
            "Capital-Equipment": "capital equipment",
            "Professional-Services": "professional services",
            "Travel-Taxes": "travel taxes",
        }

        # Only use expense_types filter for categories known to be indexed in RAG
        indexed_expense_types = {"meals"}

        try:
            import qe_tax_rag as qe

            # Normalize the expense category for RAG search
            rag_category = (
                rag_category_map.get(expense_category) if expense_category else None
            )

            # Build a more focused search query
            query_parts = [expense_description]
            if vendor_name:
                query_parts.append(vendor_name)
            if rag_category:
                query_parts.append(rag_category)
            query_parts.append("business expense tax deduction rules")
            query = " ".join(filter(None, query_parts))

            # Only use expense_types filter if the category is indexed
            # Otherwise empty filter lets RAG search across all content
            expense_types_filter = (
                [rag_category]
                if rag_category and rag_category in indexed_expense_types
                else []
            )

            logger.info(
                "RAG search query: %s, expense_types: %s",
                query,
                expense_types_filter,
            )

            # Search RAG database
            results = qe.search(
                query=query,
                expense_types=expense_types_filter,
                top_k=3,
            )

            # Phase 2: Store RAG results for programmatic citation injection
            self._last_rag_results = results if results else []

            logger.info(
                "RAG search returned %d results", len(results) if results else 0
            )
            if results:
                logger.info(
                    "RAG search raw results: %s",
                    [
                        {"id": r.citation_id, "content": r.content[:100]}
                        for r in results
                    ],
                )

            if not results:
                logger.warning("RAG search returned no results for query: %s", query)
                return "No specific CRA documents found. Rely on general tax knowledge."

            # Format results
            context_parts = ["Relevant CRA Documents Found:"]
            for i, result in enumerate(results, 1):
                # Escape quotes to prevent JSON issues
                content = result.content[:400].replace('"', '\\"')
                entry = (
                    f"\n{i}. Citation ID: {result.citation_id}\n"
                    f"   Source: {result.source_url}\n"
                    f'   Content: "{content}..."'
                )
                context_parts.append(entry)

            formatted_context = "\n".join(context_parts)
            logger.info(
                "Formatted RAG context being injected into prompt:\n%s",
                formatted_context,
            )

            return formatted_context

        except ImportError:
            logger.error("`qe_tax_rag` package not found. RAG search is disabled.")
            return "RAG system not available. Rely on general tax knowledge."
        except Exception as e:  # noqa: BLE001
            logger.warning("RAG search failed with %s: %s", type(e).__name__, e)
            return "RAG search encountered an error. Rely on general tax knowledge."

    def _inject_citations_programmatically(
        self,
        processed_items: list[dict[str, Any]],
    ) -> None:
        """Programmatically inject RAG citations into tax-relevant items.

        Phase 2 approach: Remove LLM citation extraction burden and inject
        programmatically. For demo, inject ALL retrieved citations into
        tax-relevant items.

        Args:
            processed_items: List of processed line items from LLM
        """
        if not self._last_rag_results:
            logger.debug("No RAG results available for citation injection")
            return

        # Extract all citation IDs from RAG results
        all_citations = [r.citation_id for r in self._last_rag_results]

        # Tax-relevant categories that should have CRA citations
        tax_relevant_categories = {
            "Meals & Entertainment",
            "Travel-Lodging",
            "Travel-Meals",
            "Travel-Taxes",
            "Office-Supplies",
            "Professional-Services",
            "Fuel-Vehicle",
            "Uncategorized-Review-Required",  # Include for demo/audit purposes
        }

        # Inject citations into relevant items
        for item in processed_items:
            category = item.get("category", "")
            if category in tax_relevant_categories:
                item["citations"] = all_citations
                logger.info(
                    "✅ Injected %d citation(s) into '%s' (category: %s)",
                    len(all_citations),
                    item.get("original_description", "")[:30],
                    category,
                )
            else:
                desc = item.get("original_description", "")[:30]
                logger.debug(
                    "Skipped citation for '%s' (category: %s not tax-relevant)",
                    desc,
                    category,
                )

    def _get_cra_system_message(self) -> str:
        """Get the system message for the CRA rules agent."""
        return """
You are a Canadian tax law specialist focused on CRA business expense categorization.
Your expertise includes:

1. Income Tax Act (ITA) sections and requirements
2. T2125 Statement of Business/Professional Activities form
3. CRA business expense deductibility rules
4. GST/HST Input Tax Credit eligibility
5. Audit risk assessment

Key principles you follow:
- Meals & Entertainment: 50% deductible (ITA Section 67.1)
- Travel expenses: Generally 100% deductible if business-related
- Vehicle expenses: Business portion deductible
- Office supplies: 100% deductible
- Professional fees: 100% deductible

Always consider vendor type, expense nature, and business context when categorizing.
Be conservative with high-risk categorizations and flag items for manual review
when uncertain.
"""

    def _get_metadata(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """Get metadata about the CRA categorization process."""
        metadata = super()._get_metadata(result_data)
        metadata.update(
            {
                "rules_loaded": len(self.cra_rules_service.rules),
                "category_assigned": result_data.get("category"),
                "audit_risk": result_data.get("audit_risk"),
                "rule_method": (
                    "csv_rules"
                    if "CSV Rule" in result_data.get("rule_applied", "")
                    else "agent_fallback"
                ),
            }
        )
        return metadata
