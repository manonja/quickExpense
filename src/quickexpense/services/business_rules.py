"""Business rules engine for configurable expense categorization."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quickexpense.models.business_rules import (
    BusinessRule,
    BusinessRulesConfig,
    ExpenseContext,
    RuleApplication,
    RuleResult,
)

if TYPE_CHECKING:
    from quickexpense.models.expense import LineItem

logger = logging.getLogger(__name__)


class BusinessRuleEngineError(Exception):
    """Base exception for business rule engine errors."""


class RuleConfigurationError(BusinessRuleEngineError):
    """Raised when rule configuration is invalid."""


class RuleApplicationError(BusinessRuleEngineError):
    """Raised when rule application fails."""


class BusinessRuleEngine:
    """Configurable rule engine for expense categorization."""

    def __init__(self, config_path: str | Path) -> None:
        """Initialize the rule engine with configuration."""
        self.config_path = Path(config_path)
        self.config: BusinessRulesConfig | None = None
        self.rule_history: list[RuleApplication] = []
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

    def apply_rule(
        self,
        rule: BusinessRule,
        description: str,
        vendor_name: str | None = None,
        amount: Decimal | None = None,
    ) -> RuleResult:
        """Apply a specific rule to generate categorization result."""
        # Calculate confidence score
        base_confidence = 0.8  # Base confidence for rule matches
        confidence_boost = rule.actions.confidence_boost
        confidence_score = max(0.0, min(1.0, base_confidence + confidence_boost))

        # Set business_rule_id from the rule
        actions = rule.actions.model_copy()
        actions.business_rule_id = rule.id

        result = RuleResult(
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

        return result

    def apply_fallback_rule(
        self,
        description: str,
        vendor_name: str | None = None,
        amount: Decimal | None = None,
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
        context: ExpenseContext | None = None,
    ) -> RuleResult:
        """Categorize a line item using business rules."""
        try:
            # Find matching rules
            matching_rules = self.find_matching_rules(description, vendor_name, amount)

            # Select best rule
            best_rule = self.select_best_rule(matching_rules)

            # Apply rule or fallback
            if best_rule:
                result = self.apply_rule(best_rule, description, vendor_name, amount)
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

        except Exception as e:
            logger.error("Failed to categorize line item '%s': %s", description, e)
            # Return fallback on error
            return self.apply_fallback_rule(description, vendor_name, amount)

    def categorize_line_items(
        self,
        line_items: list[LineItem],
        context: ExpenseContext | None = None,
    ) -> list[RuleResult]:
        """Categorize multiple line items using business rules."""
        results = []

        for item in line_items:
            # Extract vendor from context if available
            vendor_name = context.vendor_name if context else None

            result = self.categorize_line_item(
                description=item.description,
                vendor_name=vendor_name,
                amount=item.amount * item.quantity,  # Total amount for this line
                context=context,
            )

            results.append(result)

        return results

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
            from quickexpense.models.business_rules import RuleActions

            actions_applied = RuleActions(
                category=result.category,
                deductibility_percentage=result.deductibility_percentage,
                qb_account=result.qb_account,
                tax_treatment=result.tax_treatment,
                requires_manual_review=result.requires_manual_review,
            )

        application = RuleApplication(
            rule_id=result.business_rule_id or "fallback",
            rule_name=(
                result.rule_applied.name if result.rule_applied else "Fallback Rule"
            ),
            line_item_description=description,
            vendor_name=vendor_name,
            amount=amount,
            applied_at=datetime.now(),
            confidence_score=result.confidence_score,
            actions_applied=actions_applied,
        )

        self.rule_history.append(application)

        # Keep only last 1000 applications to prevent memory issues
        if len(self.rule_history) > 1000:
            self.rule_history = self.rule_history[-1000:]

    def get_rule_statistics(self) -> dict[str, Any]:
        """Get statistics about rule usage."""
        if not self.rule_history:
            return {"total_applications": 0}

        total_applications = len(self.rule_history)
        rule_usage = {}
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
