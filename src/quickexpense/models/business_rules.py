"""Business rules data models for configurable expense categorization."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MatchType(str, Enum):
    """Types of pattern matching for business rules."""

    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"
    KEYWORDS = "keywords"
    PATTERN = "pattern"


class TaxTreatment(str, Enum):
    """Tax treatment types for expense categorization."""

    STANDARD = "standard"
    MEALS_LIMITATION = "meals_limitation"
    CAPITAL = "capital"
    INPUT_TAX_CREDIT = "input_tax_credit"
    NON_DEDUCTIBLE = "non_deductible"


class RuleConditions(BaseModel):
    """Conditions for matching business rules."""

    description_keywords: list[str] = Field(default_factory=list)
    description_patterns: list[str] = Field(default_factory=list)
    description_regex: str | None = Field(None)
    vendor_patterns: list[str] = Field(default_factory=list)
    vendor_keywords: list[str] = Field(default_factory=list)
    amount_min: Decimal | None = Field(None, ge=0)
    amount_max: Decimal | None = Field(None, ge=0)
    category_hints: list[str] = Field(default_factory=list)

    @field_validator("amount_min", "amount_max", mode="before")
    @classmethod
    def validate_amounts(cls, v: Any) -> Decimal | None:  # noqa: ANN401
        """Convert to Decimal for precision."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        """Validate amount range."""
        if (
            self.amount_min is not None
            and self.amount_max is not None
            and self.amount_min > self.amount_max
        ):
            msg = "amount_min cannot be greater than amount_max"
            raise ValueError(msg)


class RuleActions(BaseModel):
    """Actions to apply when a business rule matches."""

    category: str = Field(..., min_length=1)
    deductibility_percentage: int = Field(..., ge=0, le=100)
    qb_account: str = Field(..., min_length=1)
    tax_treatment: TaxTreatment = Field(default=TaxTreatment.STANDARD)
    confidence_boost: float = Field(default=0.0, ge=-1.0, le=1.0)
    compliance_note: str | None = Field(None)
    requires_manual_review: bool = Field(default=False)
    account_mapping: str | None = Field(None)
    business_rule_id: str | None = Field(None)


class BusinessRule(BaseModel):
    """A configurable business rule for expense categorization."""

    id: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1, le=1000)
    name: str = Field(..., min_length=1)
    description: str | None = Field(None)
    conditions: RuleConditions
    actions: RuleActions
    enabled: bool = Field(default=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)

    def matches_description(self, description: str) -> bool:  # noqa: C901
        """Check if description matches rule conditions."""
        if not description:
            return False

        description_lower = description.lower()

        # Check keywords
        if self.conditions.description_keywords:
            for keyword in self.conditions.description_keywords:
                if keyword.lower() in description_lower:
                    return True

        # Check patterns (glob-style)
        if self.conditions.description_patterns:
            import fnmatch

            for pattern in self.conditions.description_patterns:
                if fnmatch.fnmatch(description_lower, pattern.lower()):
                    return True

        # Check regex
        if self.conditions.description_regex:
            try:
                if re.search(
                    self.conditions.description_regex, description, re.IGNORECASE
                ):
                    return True
            except re.error:
                # Invalid regex, skip
                pass

        return False

    def matches_vendor(self, vendor_name: str) -> bool:
        """Check if vendor matches rule conditions."""
        if not vendor_name:
            return False

        vendor_lower = vendor_name.lower()

        # Check vendor patterns
        if self.conditions.vendor_patterns:
            import fnmatch

            for pattern in self.conditions.vendor_patterns:
                if fnmatch.fnmatch(vendor_lower, pattern.lower()):
                    return True

        # Check vendor keywords
        if self.conditions.vendor_keywords:
            for keyword in self.conditions.vendor_keywords:
                if keyword.lower() in vendor_lower:
                    return True

        return False

    def matches_amount(self, amount: Decimal) -> bool:
        """Check if amount matches rule conditions."""
        if (
            self.conditions.amount_min is not None
            and amount < self.conditions.amount_min
        ):
            return False

        return not (
            self.conditions.amount_max is not None
            and amount > self.conditions.amount_max
        )

    def matches(
        self,
        description: str,
        vendor_name: str | None = None,
        amount: Decimal | None = None,
    ) -> bool:
        """Check if all conditions match."""
        if not self.enabled:
            return False

        # Description is required to match
        if not self.matches_description(description):
            return False

        # Vendor matching (if specified)
        if (
            vendor_name
            and (self.conditions.vendor_patterns or self.conditions.vendor_keywords)
            and not self.matches_vendor(vendor_name)
        ):
            return False

        # Amount matching (if specified)
        return not (
            amount is not None
            and (
                self.conditions.amount_min is not None
                or self.conditions.amount_max is not None
            )
            and not self.matches_amount(amount)
        )


class RuleApplication(BaseModel):
    """Record of a rule being applied to a line item."""

    rule_id: str
    rule_name: str
    line_item_description: str
    vendor_name: str | None = Field(None)
    amount: Decimal | None = Field(None)
    applied_at: datetime
    confidence_score: float = Field(ge=0, le=1)
    actions_applied: RuleActions

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal | None:  # noqa: ANN401
        """Convert to Decimal for precision."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v


class RuleResult(BaseModel):
    """Result of applying business rules to a line item."""

    rule_applied: BusinessRule | None = Field(None)
    category: str
    deductibility_percentage: int = Field(ge=0, le=100)
    qb_account: str
    tax_treatment: TaxTreatment
    confidence_score: float = Field(ge=0, le=1)
    requires_manual_review: bool = Field(default=False)
    compliance_note: str | None = Field(None)
    account_mapping: str | None = Field(None)
    business_rule_id: str | None = Field(None)
    is_fallback: bool = Field(default=False)


class FallbackRules(BaseModel):
    """Fallback rules for unmatched expenses."""

    unknown_expense: RuleActions


class BusinessRulesConfig(BaseModel):
    """Complete business rules configuration."""

    version: str = Field(..., min_length=1)
    rules: list[BusinessRule]
    fallback_rules: FallbackRules
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_rule_by_id(self, rule_id: str) -> BusinessRule | None:
        """Get a rule by its ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def get_enabled_rules(self) -> list[BusinessRule]:
        """Get all enabled rules sorted by priority (highest first)."""
        enabled_rules = [rule for rule in self.rules if rule.enabled]
        return sorted(enabled_rules, key=lambda r: r.priority, reverse=True)

    def validate_rule_priorities(self) -> list[str]:
        """Validate that rule priorities are unique."""
        priorities = [rule.priority for rule in self.rules if rule.enabled]
        duplicates = []
        seen = set()

        for priority in priorities:
            if priority in seen:
                duplicates.append(f"Duplicate priority {priority}")
            else:
                seen.add(priority)

        return duplicates


class ExpenseContext(BaseModel):
    """Context information for rule matching."""

    vendor_name: str | None = Field(None)
    transaction_date: datetime | None = Field(None)
    total_amount: Decimal | None = Field(None)
    currency: str = Field(default="USD")
    payment_method: str | None = Field(None)
    business_purpose: str | None = Field(None)
    location: str | None = Field(None)

    @field_validator("total_amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal | None:  # noqa: ANN401
        """Convert to Decimal for precision."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v
