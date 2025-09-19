"""Business rules engine for expense categorization with provincial tax context."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from quickexpense.models.business_rules import (
    BusinessRule,
    BusinessRulesConfig,
    ExpenseContext,
    RuleActions,
    RuleApplication,
    RuleResult,
)
from quickexpense.models.tax import (
    EntityAwareExpenseMapping,
    ProvinceCode,
    ProvinceDetection,
)
from quickexpense.services.provincial_tax import ProvincialTaxService

logger = logging.getLogger(__name__)

# Constants
RULE_HISTORY_LIMIT = 1000


class BusinessRuleEngineError(Exception):
    """Base exception for business rule engine errors."""


class RuleConfigurationError(BusinessRuleEngineError):
    """Raised when rule configuration is invalid."""


class RuleApplicationError(BusinessRuleEngineError):
    """Raised when rule application fails."""


class BusinessRuleEngine:
    """Rule engine for expense categorization with provincial tax awareness."""

    def __init__(
        self,
        config_path: str | Path,
        entity_type: str = "sole_proprietorship",
        default_province: ProvinceCode = ProvinceCode.BC,
    ) -> None:
        """Initialize the rule engine with configuration and tax context."""
        self.config_path = Path(config_path)
        self.config: BusinessRulesConfig | None = None
        self.rule_history: list[RuleApplication] = []
        self.entity_type = entity_type
        self.provincial_tax_service = ProvincialTaxService(
            default_province=default_province
        )
        self._load_rules()

    def _load_rules(self) -> None:
        """Load and validate business rules from configuration file."""
        try:
            if not self.config_path.exists():
                msg = f"Rule configuration file not found: {self.config_path}"
                raise RuleConfigurationError(msg)

            with self.config_path.open() as f:
                config_data = json.load(f)

            self.config = BusinessRulesConfig(**config_data)

            # Validate rule consistency
            validation_errors = self.config.validate_rule_priorities()
            if validation_errors:
                logger.warning("Rule validation warnings: %s", validation_errors)

            logger.info(
                "Loaded %d business rules from %s",
                len(self.config.rules),
                self.config_path,
            )

        except (json.JSONDecodeError, FileNotFoundError) as e:
            msg = f"Failed to load rule configuration: {e}"
            raise RuleConfigurationError(msg) from e
        except Exception as e:
            msg = f"Unexpected error loading rules: {e}"
            raise RuleConfigurationError(msg) from e

    def reload_rules(self) -> None:
        """Hot-reload rules from configuration file."""
        logger.info("Reloading business rules from %s", self.config_path)
        old_rule_count = len(self.config.rules) if self.config else 0

        self._load_rules()

        new_rule_count = len(self.config.rules) if self.config else 0
        logger.info(
            "Rules reloaded: %d rules (was %d)",
            new_rule_count,
            old_rule_count,
        )

    def find_matching_rules(
        self,
        description: str,
        vendor_name: str | None = None,
        amount: Decimal | None = None,
    ) -> list[BusinessRule]:
        """Find all rules that match the given criteria."""
        if not self.config:
            msg = "Rules not loaded"
            raise RuleApplicationError(msg)

        matching_rules = []
        enabled_rules = self.config.get_enabled_rules()

        for rule in enabled_rules:
            if rule.matches(description, vendor_name, amount):
                matching_rules.append(rule)
                logger.debug(
                    "Rule '%s' matches description: %s",
                    rule.name,
                    description,
                )

        return matching_rules

    def select_best_rule(
        self, matching_rules: list[BusinessRule]
    ) -> BusinessRule | None:
        """Select the best rule from matching rules based on priority."""
        if not matching_rules:
            return None

        # Rules are already sorted by priority (highest first)
        best_rule = matching_rules[0]

        if len(matching_rules) > 1:
            logger.info(
                "Multiple rules matched, selected highest priority: %s (priority %d)",
                best_rule.name,
                best_rule.priority,
            )

            # Log conflicts for audit
            other_rules = [r.name for r in matching_rules[1:]]
            logger.debug("Conflicting rules: %s", other_rules)

        return best_rule

    def select_best_rule_with_vendor_context(
        self, matching_rules: list[BusinessRule], vendor_name: str | None = None
    ) -> BusinessRule | None:
        """Select the best rule with vendor context awareness."""
        if not matching_rules:
            return None

        # If no vendor context, fall back to standard selection
        if not vendor_name:
            return self.select_best_rule(matching_rules)

        # Separate vendor-specific rules from generic rules
        vendor_specific_rules = []
        generic_rules = []

        for rule in matching_rules:
            if rule.conditions.vendor_patterns or rule.conditions.vendor_keywords:
                # Check if this rule actually matches the vendor
                if rule.matches_vendor(vendor_name):
                    vendor_specific_rules.append(rule)
                else:
                    # Rule has vendor patterns but doesn't match this vendor
                    continue
            else:
                generic_rules.append(rule)

        # Prefer vendor-specific rules over generic rules
        if vendor_specific_rules:
            best_rule = vendor_specific_rules[0]  # Already sorted by priority
            if len(vendor_specific_rules) > 1:
                logger.info(
                    (
                        "Multiple vendor-specific rules matched for %s, "
                        "selected: %s (priority %d)"
                    ),
                    vendor_name,
                    best_rule.name,
                    best_rule.priority,
                )
            else:
                logger.info(
                    "Selected vendor-specific rule for %s: %s",
                    vendor_name,
                    best_rule.name,
                )
            return best_rule

        # Fall back to generic rules if no vendor-specific matches
        if generic_rules:
            best_rule = generic_rules[0]
            logger.debug(
                "No vendor-specific rules matched for %s, using generic rule: %s",
                vendor_name,
                best_rule.name,
            )
            return best_rule

        return None

    def _calculate_confidence_with_vendor_context(
        self, rule: BusinessRule, vendor_name: str | None = None
    ) -> float:
        """Calculate confidence score considering vendor context."""
        base_confidence = 0.8  # Base confidence for rule matches
        confidence_boost = rule.actions.confidence_boost

        # Start with base calculation
        confidence_score = base_confidence + confidence_boost

        # Apply vendor context adjustments
        if vendor_name:
            # Check if rule has vendor patterns
            has_vendor_patterns = (
                rule.conditions.vendor_patterns or rule.conditions.vendor_keywords
            )

            if has_vendor_patterns:
                # Rule is vendor-specific and we have vendor context
                if rule.matches_vendor(vendor_name):
                    # Perfect match: vendor-specific rule matching the vendor
                    confidence_score += 0.05  # Extra boost for vendor alignment
                    logger.debug(
                        "Vendor-specific rule %s matches vendor %s: +0.05 confidence",
                        rule.name,
                        vendor_name,
                    )
                else:
                    # This shouldn't happen due to filtering, but just in case
                    confidence_score -= 0.1  # Penalty for vendor mismatch
                    logger.warning(
                        (
                            "Vendor-specific rule %s does not match vendor %s: "
                            "-0.1 confidence"
                        ),
                        rule.name,
                        vendor_name,
                    )
            else:
                # Generic rule applied to vendor context
                # No penalty, but also no bonus
                logger.debug(
                    (
                        "Generic rule %s applied to vendor %s: "
                        "no vendor context adjustment"
                    ),
                    rule.name,
                    vendor_name,
                )

        # Ensure confidence stays within bounds
        return max(0.0, min(1.0, confidence_score))

    def validate_vendor_category_alignment(
        self, rule: BusinessRule, vendor_name: str | None = None
    ) -> tuple[bool, str | None]:
        """Validate if the rule's category aligns with the vendor type."""
        if not vendor_name:
            return True, None

        vendor_lower = vendor_name.lower()
        category = rule.actions.category.lower()

        # Known vendor type patterns and their expected categories
        hotel_patterns = [
            "hotel",
            "inn",
            "resort",
            "motel",
            "lodge",
            "marriott",
            "hilton",
            "hyatt",
            "courtyard",
            "sheraton",
            "westin",
        ]
        restaurant_patterns = [
            "restaurant",
            "cafe",
            "bistro",
            "bar",
            "pub",
            "eatery",
            "kitchen",
            "dining",
        ]
        transport_patterns = ["taxi", "uber", "lyft", "airline", "airport"]

        # Check for potential misalignments
        warning_message = None

        if any(pattern in vendor_lower for pattern in hotel_patterns):
            if "professional" in category:
                warning_message = (
                    f"Hotel vendor '{vendor_name}' categorized as "
                    f"'{rule.actions.category}' - consider Travel-Lodging "
                    f"for hotel fees"
                )
        elif (
            any(pattern in vendor_lower for pattern in restaurant_patterns)
            and "lodging" in category
        ):
            warning_message = (
                f"Restaurant vendor '{vendor_name}' categorized as "
                f"'{rule.actions.category}' - consider Travel-Meals category"
            )
        elif (
            any(pattern in vendor_lower for pattern in transport_patterns)
            and "professional" in category
        ):
            warning_message = (
                f"Transportation vendor '{vendor_name}' categorized as "
                f"'{rule.actions.category}' - consider Travel-Transportation category"
            )

        return warning_message is None, warning_message

    def apply_rule(
        self,
        rule: BusinessRule,
        description: str,  # noqa: ARG002
        vendor_name: str | None = None,
        amount: Decimal | None = None,  # noqa: ARG002
    ) -> RuleResult:
        """Apply a specific rule to generate categorization result."""
        # Calculate confidence score with vendor context
        confidence_score = self._calculate_confidence_with_vendor_context(
            rule, vendor_name
        )

        # Set business_rule_id from the rule
        actions = rule.actions.model_copy()
        actions.business_rule_id = rule.id

        return RuleResult(
            rule_applied=rule,
            category=actions.category,
            deductibility_percentage=actions.deductibility_percentage,
            qb_account=actions.qb_account,
            tax_treatment=actions.tax_treatment,
            confidence_score=confidence_score,
            requires_manual_review=actions.requires_manual_review,
            compliance_note=actions.compliance_note,
            account_mapping=actions.account_mapping,
            business_rule_id=actions.business_rule_id,
            is_fallback=False,
        )

    def apply_fallback_rule(
        self,
        description: str,
        vendor_name: str | None = None,  # noqa: ARG002
        amount: Decimal | None = None,  # noqa: ARG002
    ) -> RuleResult:
        """Apply fallback rule for unmatched items."""
        if not self.config:
            msg = "Rules not loaded"
            raise RuleApplicationError(msg)

        fallback = self.config.fallback_rules.unknown_expense

        result = RuleResult(
            rule_applied=None,
            category=fallback.category,
            deductibility_percentage=fallback.deductibility_percentage,
            qb_account=fallback.qb_account,
            tax_treatment=fallback.tax_treatment,
            confidence_score=0.3,  # Low confidence for fallback
            requires_manual_review=fallback.requires_manual_review,
            compliance_note=fallback.compliance_note,
            account_mapping=fallback.account_mapping,
            business_rule_id=fallback.business_rule_id,
            is_fallback=True,
        )

        logger.info(
            "Applied fallback rule for unmatched item: %s",
            description,
        )

        return result

    def categorize_line_item(
        self,
        description: str,
        vendor_name: str | None = None,
        amount: Decimal | None = None,
        context: ExpenseContext | None = None,  # noqa: ARG002
    ) -> RuleResult:
        """Categorize a line item using business rules with vendor context awareness."""
        try:
            # Find matching rules
            matching_rules = self.find_matching_rules(description, vendor_name, amount)

            # Select best rule with vendor context awareness
            best_rule = self.select_best_rule_with_vendor_context(
                matching_rules, vendor_name
            )

            # Apply rule or fallback
            if best_rule:
                result = self.apply_rule(best_rule, description, vendor_name, amount)

                # Validate vendor-category alignment and add warnings if needed
                is_aligned, warning_message = self.validate_vendor_category_alignment(
                    best_rule, vendor_name
                )

                if not is_aligned and warning_message:
                    logger.warning(
                        "Vendor-category alignment warning: %s", warning_message
                    )
                    # Could add warning to result if needed for CLI display

            else:
                result = self.apply_fallback_rule(description, vendor_name, amount)

            # Log rule application
            self._log_rule_application(
                description,
                vendor_name,
                amount,
                result,
            )

            return result

        except Exception as e:  # noqa: BLE001
            logger.error("Failed to categorize line item '%s': %s", description, e)
            # Return fallback on error
            return self.apply_fallback_rule(description, vendor_name, amount)

    def categorize_line_items(
        self,
        line_items: list[Any],  # Accept both expense.LineItem and receipt.LineItem
        context: ExpenseContext | None = None,
    ) -> list[RuleResult]:
        """Categorize multiple line items using business rules."""
        results = []

        for item in line_items:
            # Extract vendor from context if available
            vendor_name = context.vendor_name if context else None

            # Handle both expense.LineItem and receipt.LineItem models
            if hasattr(item, "amount"):
                # expense.LineItem model: amount + quantity
                total_amount = item.amount * item.quantity
            elif hasattr(item, "total_price"):
                # receipt.LineItem model: total_price
                total_amount = item.total_price
            else:
                # Fallback: try to extract amount from item
                logger.warning("Unknown LineItem type, attempting fallback")
                total_amount = getattr(
                    item, "amount", getattr(item, "total_price", Decimal(0))
                )

            result = self.categorize_line_item(
                description=item.description,
                vendor_name=vendor_name,
                amount=total_amount,
                context=context,
            )

            results.append(result)

        return results

    def categorize_with_provincial_context(
        self,
        description: str,
        context: ExpenseContext,
    ) -> tuple[RuleResult, ProvinceDetection, EntityAwareExpenseMapping]:
        """Categorize expense with provincial tax context and entity awareness."""

        # 1. Detect province from vendor information
        province_detection = self.provincial_tax_service.detect_province(
            vendor_address=context.vendor_address, postal_code=context.postal_code
        )

        logger.info(
            "Province detected: %s (confidence: %.2f, method: %s)",
            province_detection.province.value,
            province_detection.confidence,
            province_detection.detection_method,
        )

        # 2. Apply business rules with vendor context
        rule_result = self.categorize_line_item(
            description=description,
            vendor_name=context.vendor_name,
            amount=context.total_amount,
            context=context,
        )

        # 3. Get entity-aware expense mapping (T2125 for sole proprietorship)
        entity_mapping = EntityAwareExpenseMapping.get_mapping(
            entity_type=self.entity_type, category=rule_result.category
        )

        logger.info(
            "Entity-aware mapping: %s → T2125 Line %s (%s)",
            rule_result.category,
            entity_mapping.form_line_item,
            entity_mapping.form_line_description,
        )

        # 4. Log provincial context for audit
        logger.debug(
            "Provincial context: %s %s → %s (T2125 Line %s)",
            province_detection.province.value,
            rule_result.category,
            entity_mapping.form_line_description,
            entity_mapping.form_line_item,
        )

        return rule_result, province_detection, entity_mapping

    def get_t2125_summary(
        self, results: list[tuple[RuleResult, EntityAwareExpenseMapping]]
    ) -> dict[str, Any]:
        """Generate T2125 form summary from categorized expenses."""

        total_deductible = Decimal("0.00")

        # Group by T2125 line items
        line_item_totals: dict[str, dict[str, Any]] = {}

        for _rule_result, entity_mapping in results:
            line_item = entity_mapping.form_line_item

            if line_item not in line_item_totals:
                line_item_totals[line_item] = {
                    "description": entity_mapping.form_line_description,
                    "total_amount": Decimal("0.00"),
                    "deductible_amount": Decimal("0.00"),
                    "deductibility_percentage": entity_mapping.deductibility_percentage,
                    "count": 0,
                    "ita_reference": entity_mapping.ita_reference,
                }

            # Calculate amounts (assuming amount is available in rule context)
            # This would be enhanced with actual expense amounts in real implementation
            expense_amount = Decimal(
                "100.00"
            )  # Placeholder - would come from actual expense
            deductible_amount = expense_amount * Decimal(
                str(entity_mapping.deductibility_percentage / 100)
            )

            line_item_totals[line_item]["total_amount"] += expense_amount
            line_item_totals[line_item]["deductible_amount"] += deductible_amount
            line_item_totals[line_item]["count"] += 1

            total_deductible += deductible_amount

        return {
            "entity_type": self.entity_type,
            "tax_form": "T2125",
            "line_items": line_item_totals,
            "total_deductible": total_deductible,
            "requires_review": any(
                result.requires_manual_review for result, _ in results
            ),
        }

    def validate_provincial_compliance(
        self, rule_result: RuleResult, province_detection: ProvinceDetection
    ) -> tuple[bool, list[str]]:
        """Validate if categorization complies with provincial regulations."""

        compliance_issues = []

        # Get provincial tax configuration
        try:
            self.provincial_tax_service.get_provincial_config(
                province_detection.province
            )

            # Check for province-specific compliance requirements
            if (
                province_detection.province == ProvinceCode.QC
                and "professional" in rule_result.category.lower()
            ):
                msg = (
                    "Quebec professional services may require QST "
                    "registration verification"
                )
                compliance_issues.append(msg)

            # General GST/HST compliance checks
            if rule_result.category in ["Travel-Meals", "Entertainment"] and (
                not rule_result.compliance_note
                or "50%" not in rule_result.compliance_note
            ):
                msg = (
                    "Meals and entertainment are limited to 50% deductibility "
                    "per ITA Section 67.1"
                )
                compliance_issues.append(msg)

            # Province detection confidence warning
            confidence_threshold = 0.8
            if province_detection.confidence < confidence_threshold:
                msg = (
                    f"Low confidence in province detection "
                    f"({province_detection.confidence:.2f}) - "
                    f"verify {province_detection.province.value} tax rates manually"
                )
                compliance_issues.append(msg)

        except Exception as e:  # noqa: BLE001
            compliance_issues.append(f"Error validating provincial compliance: {e}")

        is_compliant = len(compliance_issues) == 0
        return is_compliant, compliance_issues

    def _log_rule_application(
        self,
        description: str,
        vendor_name: str | None,
        amount: Decimal | None,
        result: RuleResult,
    ) -> None:
        """Log rule application for audit purposes."""
        # Create fallback actions for logging
        if result.rule_applied:
            actions_applied = result.rule_applied.actions
        else:
            # Create fallback actions
            actions_applied = RuleActions(
                category=result.category,
                deductibility_percentage=result.deductibility_percentage,
                qb_account=result.qb_account,
                tax_treatment=result.tax_treatment,
                requires_manual_review=result.requires_manual_review,
                compliance_note=None,
                account_mapping=None,
                business_rule_id=None,
            )

        application = RuleApplication(
            rule_id=result.business_rule_id or "fallback",
            rule_name=(
                result.rule_applied.name if result.rule_applied else "Fallback Rule"
            ),
            line_item_description=description,
            vendor_name=vendor_name,
            amount=amount,
            applied_at=datetime.now(tz=UTC),
            confidence_score=result.confidence_score,
            actions_applied=actions_applied,
        )

        self.rule_history.append(application)

        # Keep only last RULE_HISTORY_LIMIT applications to prevent memory issues
        if len(self.rule_history) > RULE_HISTORY_LIMIT:
            self.rule_history = self.rule_history[-RULE_HISTORY_LIMIT:]

    def get_rule_statistics(self) -> dict[str, Any]:
        """Get statistics about rule usage."""
        if not self.rule_history:
            return {"total_applications": 0}

        total_applications = len(self.rule_history)
        rule_usage: dict[str, int] = {}
        fallback_count = 0

        for application in self.rule_history:
            if application.rule_id == "fallback":
                fallback_count += 1
            else:
                rule_usage[application.rule_id] = (
                    rule_usage.get(application.rule_id, 0) + 1
                )

        average_confidence = (
            sum(app.confidence_score for app in self.rule_history) / total_applications
        )

        return {
            "total_applications": total_applications,
            "rule_usage": rule_usage,
            "fallback_count": fallback_count,
            "fallback_percentage": (fallback_count / total_applications) * 100,
            "average_confidence": round(average_confidence, 3),
            "unique_rules_used": len(rule_usage),
        }

    def validate_configuration(self) -> list[str]:
        """Validate the current rule configuration."""
        if not self.config:
            return ["No configuration loaded"]

        errors = []

        # Check for duplicate priorities
        priority_errors = self.config.validate_rule_priorities()
        errors.extend(priority_errors)

        # Check for empty rules
        if not self.config.rules:
            errors.append("No rules defined")

        # Check for rules with no conditions
        for rule in self.config.rules:
            conditions = rule.conditions
            has_conditions = (
                conditions.description_keywords
                or conditions.description_patterns
                or conditions.description_regex
                or conditions.vendor_patterns
                or conditions.vendor_keywords
                or conditions.amount_min is not None
                or conditions.amount_max is not None
            )

            if not has_conditions:
                errors.append(f"Rule '{rule.id}' has no matching conditions")

        return errors
