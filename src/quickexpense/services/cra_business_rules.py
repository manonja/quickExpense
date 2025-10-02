"""CRA Business Rules Service for CSV-based rule management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CRARule(BaseModel):
    """Model for a single CRA business rule."""

    category: str = Field(..., description="Business expense category")
    t2125_line: str = Field(..., description="T2125 tax form line number")
    deductibility_rate: int = Field(
        ..., ge=0, le=100, description="Deductibility percentage (0-100)"
    )
    ita_section: str = Field(..., description="Income Tax Act section reference")
    description: str = Field(..., description="Rule description")
    keywords: str = Field(..., description="Comma-separated keywords for matching")
    examples: str = Field(..., description="Example vendors/situations")
    audit_risk: str = Field(
        ..., pattern="^(LOW|MEDIUM|HIGH)$", description="Audit risk level"
    )
    confidence_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Minimum confidence for auto-categorization"
    )

    @property
    def keyword_list(self) -> list[str]:
        """Return keywords as a cleaned list."""
        return [k.strip().lower() for k in self.keywords.split(";") if k.strip()]

    @property
    def example_list(self) -> list[str]:
        """Return examples as a cleaned list."""
        return [e.strip() for e in self.examples.split(";") if e.strip()]


class RuleMatchResult(BaseModel):
    """Result of a rule matching operation."""

    rule: CRARule
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)
    matching_reason: str = Field(default="")


class CRABusinessRulesService:
    """Service for loading and querying CRA business rules from CSV."""

    def __init__(self, rules_csv_path: str | Path | None = None) -> None:
        """Initialize the CRA business rules service.

        Args:
            rules_csv_path: Path to the CSV rules file. Defaults to config/cra_rules.csv
        """
        if rules_csv_path is None:
            # Default to the config directory
            base_path = Path(__file__).parent.parent.parent.parent
            rules_csv_path = base_path / "config" / "cra_rules.csv"

        self.rules_csv_path = Path(rules_csv_path)
        self.rules: list[CRARule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """Load rules from CSV file."""
        try:
            if not self.rules_csv_path.exists():
                msg = f"CRA rules CSV file not found: {self.rules_csv_path}"
                raise FileNotFoundError(msg)

            # Load CSV with pandas for better handling
            rules_df = pd.read_csv(self.rules_csv_path)

            # Validate required columns
            required_columns = {
                "category",
                "t2125_line",
                "deductibility_rate",
                "ita_section",
                "description",
                "keywords",
                "examples",
                "audit_risk",
                "confidence_threshold",
            }

            missing_columns = required_columns - set(rules_df.columns)
            if missing_columns:
                msg = f"Missing required columns in CSV: {missing_columns}"
                raise ValueError(msg)

            # Convert to CRARule objects
            self.rules = []
            for _, row in rules_df.iterrows():
                try:
                    rule = CRARule(
                        category=str(row["category"]),
                        t2125_line=str(row["t2125_line"]),
                        deductibility_rate=int(row["deductibility_rate"]),
                        ita_section=str(row["ita_section"]),
                        description=str(row["description"]),
                        keywords=str(row["keywords"]),
                        examples=str(row["examples"]),
                        audit_risk=str(row["audit_risk"]),
                        confidence_threshold=float(row["confidence_threshold"]),
                    )
                    self.rules.append(rule)
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(
                        "Failed to parse rule row %s: %s",
                        row.to_dict(),
                        e,
                        exc_info=True,
                    )

            logger.info(
                "Loaded %d CRA business rules from %s",
                len(self.rules),
                self.rules_csv_path,
            )

        except (FileNotFoundError, ValueError, pd.errors.ParserError):
            logger.exception(
                "Failed to load CRA rules from %s",
                self.rules_csv_path,
            )
            # Load fallback rule for unknown expenses
            self.rules = [
                CRARule(
                    category="General Business Expense",
                    t2125_line="9270",
                    deductibility_rate=100,
                    ita_section="Standard",
                    description="Unknown expense type - requires manual review",
                    keywords="",
                    examples="",
                    audit_risk="HIGH",
                    confidence_threshold=0.50,
                )
            ]

    def find_matching_rules(
        self,
        vendor_name: str,
        line_item_descriptions: list[str],
        amount: float | None = None,  # noqa: ARG002
    ) -> list[RuleMatchResult]:
        """Find rules that match the given expense information.

        Args:
            vendor_name: Name of the vendor
            line_item_descriptions: List of line item descriptions
            amount: Transaction amount (optional)

        Returns:
            List of matching rules sorted by confidence score (highest first)
        """
        matches: list[RuleMatchResult] = []

        # Combine all text for keyword matching
        combined_text = f"{vendor_name} {' '.join(line_item_descriptions)}".lower()

        for rule in self.rules:
            confidence_score = 0.0
            matched_keywords: list[str] = []
            matching_reasons: list[str] = []

            # Check keyword matches
            for keyword in rule.keyword_list:
                if keyword and keyword in combined_text:
                    confidence_score += 0.2  # Base score per keyword match
                    matched_keywords.append(keyword)

            # Boost confidence if vendor name contains category-related terms
            vendor_lower = vendor_name.lower()
            category_terms = {
                "Travel-Lodging": ["hotel", "inn", "resort", "motel", "lodge"],
                "Travel-Meals": ["restaurant", "cafe", "bistro", "food"],
                "Vehicle-Fuel": ["petro", "shell", "esso", "gas", "fuel"],
                "Office Supplies": ["office", "supply", "depot", "staples"],
                "Software": ["microsoft", "adobe", "google", "software"],
            }

            if rule.category in category_terms:
                for term in category_terms[rule.category]:
                    if term in vendor_lower:
                        confidence_score += 0.15
                        matching_reasons.append(f"vendor contains '{term}'")

            # Apply amount-based adjustments if specified
            # (This would be enhanced based on future CSV columns for amount ranges)

            if confidence_score > 0:
                matches.append(
                    RuleMatchResult(
                        rule=rule,
                        confidence_score=min(confidence_score, 1.0),  # Cap at 1.0
                        matched_keywords=matched_keywords,
                        matching_reason=(
                            "; ".join(matching_reasons)
                            if matching_reasons
                            else f"matched keywords: {', '.join(matched_keywords)}"
                        ),
                    )
                )

        # Sort by confidence score (highest first)
        matches.sort(key=lambda x: x.confidence_score, reverse=True)

        # If no matches found, return the fallback rule
        if not matches and self.rules:
            fallback_rule = next(
                (r for r in self.rules if r.category == "General Business Expense"),
                self.rules[0],  # Use first rule as ultimate fallback
            )
            matches.append(
                RuleMatchResult(
                    rule=fallback_rule,
                    confidence_score=0.1,
                    matched_keywords=[],
                    matching_reason="No specific rules matched - using fallback",
                )
            )

        return matches

    def get_best_rule_match(
        self,
        vendor_name: str,
        line_item_descriptions: list[str],
        amount: float | None = None,
    ) -> RuleMatchResult:
        """Get the best matching rule for the given expense.

        Args:
            vendor_name: Name of the vendor
            line_item_descriptions: List of line item descriptions
            amount: Transaction amount (optional)

        Returns:
            The best matching rule result
        """
        matches = self.find_matching_rules(vendor_name, line_item_descriptions, amount)
        return matches[0] if matches else self.get_fallback_rule()

    def get_rules_by_category(self, category: str) -> list[CRARule]:
        """Get all rules for a specific category.

        Args:
            category: The expense category

        Returns:
            List of rules for the category
        """
        return [rule for rule in self.rules if rule.category == category]

    def get_all_categories(self) -> list[str]:
        """Get all available expense categories.

        Returns:
            List of unique categories
        """
        return list({rule.category for rule in self.rules})

    def get_fallback_rule(self) -> RuleMatchResult:
        """Get the fallback rule for unknown expenses."""
        fallback_rule = CRARule(
            category="General Business Expense",
            t2125_line="9270",
            deductibility_rate=100,
            ita_section="Standard",
            description="Unknown expense type - requires manual review",
            keywords="",
            examples="",
            audit_risk="HIGH",
            confidence_threshold=0.50,
        )

        return RuleMatchResult(
            rule=fallback_rule,
            confidence_score=0.1,
            matched_keywords=[],
            matching_reason="Fallback rule for unknown expense type",
        )

    def reload_rules(self) -> None:
        """Reload rules from the CSV file."""
        self._load_rules()

    def get_rules_summary(self) -> dict[str, Any]:
        """Get a summary of loaded rules.

        Returns:
            Dictionary with rule statistics
        """
        categories = self.get_all_categories()
        audit_risks = [rule.audit_risk for rule in self.rules]

        return {
            "total_rules": len(self.rules),
            "categories": categories,
            "category_count": len(categories),
            "audit_risk_distribution": {
                risk: audit_risks.count(risk) for risk in ["LOW", "MEDIUM", "HIGH"]
            },
            "csv_path": str(self.rules_csv_path),
        }
