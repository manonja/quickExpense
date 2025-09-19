# PRE-107: Business Rules Configuration System

**Type:** Story
**Priority:** High
**Effort:** 5 Story Points
**Sprint:** Foundation Layer

## User Story
**As a** small business owner
**I want** expense categorization rules to be configurable without code changes
**So that** I can adapt the system to different business types, tax jurisdictions, and accounting requirements without developer intervention

## Business Value
- **Problem:** Current system has hardcoded categorization logic, making it inflexible for different business needs
- **Impact:** Requires developer changes for new expense types, cannot adapt to different tax rules or business categories
- **Solution:** JSON-based rule engine allowing non-technical configuration of expense processing logic

## Description
Create a flexible, configuration-driven business rules engine that determines how expenses are categorized, which deductibility percentages apply, and how line items map to QuickBooks accounts. The system should support pattern matching, priority rules, and extensible rule types for different business scenarios.

## Acceptance Criteria

### AC1: JSON-Based Rule Configuration
- [ ] Rules stored in JSON configuration file (`config/business_rules.json`)
- [ ] Rules support pattern matching on line item descriptions
- [ ] Rules include priority ordering for conflict resolution
- [ ] Rules support multiple matching criteria (vendor, amount ranges, keywords)
- [ ] Configuration validates against JSON schema on load
- [ ] Rules support environment-specific overrides (dev/staging/prod)

### AC2: Rule Engine Core Functionality
- [ ] Rule engine processes line items and applies matching rules
- [ ] Engine supports exact match, contains, regex, and keyword matching
- [ ] Engine applies highest priority rule when multiple rules match
- [ ] Engine logs which rules were applied for audit purposes
- [ ] Engine supports fallback rules for unmatched items
- [ ] Engine validates rule consistency and reports conflicts

### AC3: Expense Categorization Rules
- [ ] Rules determine expense category (Travel-Lodging, Travel-Meals, Office Supplies, etc.)
- [ ] Rules set deductibility percentage (0-100%)
- [ ] Rules map to specific QuickBooks accounts
- [ ] Rules specify tax treatment (standard, meals_limitation, capital, etc.)
- [ ] Rules support conditional logic based on vendor or amount
- [ ] Rules include confidence scoring for AI validation

### AC4: Canadian Tax Compliance Rules (Default Set)
- [ ] Pre-configured rules for Canadian tax requirements (CRA compliance)
- [ ] Meal expense rules with 50% deductibility (ITA Section 67.1)
- [ ] GST/HST Input Tax Credit rules
- [ ] Travel expense categorization (accommodation vs meals)
- [ ] Capital asset vs expense determination rules
- [ ] Foreign currency transaction handling rules

### AC5: Rule Management Service
- [ ] Service to load and validate business rules from configuration
- [ ] Service to apply rules to expense line items
- [ ] Service to handle rule conflicts and priorities
- [ ] Service to track rule application history
- [ ] Service to validate new rules before applying
- [ ] Service supports hot-reloading of rules (without restart)

## Technical Implementation

### Files to Create
- `src/quickexpense/services/business_rules.py` - Rule engine implementation
- `src/quickexpense/models/business_rules.py` - Rule data models
- `config/business_rules.json` - Default rule configuration
- `config/business_rules.schema.json` - JSON schema for validation
- `tests/services/test_business_rules.py` - Comprehensive tests

### Rule Configuration Schema
```json
{
  "version": "1.0",
  "rules": [
    {
      "id": "hotel_accommodation",
      "priority": 100,
      "name": "Hotel Accommodation Charges",
      "conditions": {
        "description_keywords": ["room charge", "accommodation", "hotel fee"],
        "vendor_patterns": ["*hotel*", "*inn*", "*resort*"],
        "amount_range": {"min": 50.00, "max": 1000.00}
      },
      "actions": {
        "category": "Travel-Lodging",
        "deductibility_percentage": 100,
        "qb_account": "Travel - Lodging",
        "tax_treatment": "standard",
        "confidence_boost": 0.1
      }
    },
    {
      "id": "restaurant_meals",
      "priority": 90,
      "name": "Restaurant and Meal Charges",
      "conditions": {
        "description_keywords": ["restaurant", "meal", "dining", "food", "coffee"],
        "vendor_patterns": ["*restaurant*", "*cafe*", "*bistro*"]
      },
      "actions": {
        "category": "Travel-Meals",
        "deductibility_percentage": 50,
        "qb_account": "Travel - Meals & Entertainment",
        "tax_treatment": "meals_limitation",
        "compliance_note": "CRA ITA Section 67.1 - 50% limitation applies"
      }
    }
  ],
  "fallback_rules": {
    "unknown_expense": {
      "category": "General Business Expense",
      "deductibility_percentage": 100,
      "qb_account": "Other Business Expenses",
      "tax_treatment": "standard",
      "requires_manual_review": true
    }
  }
}
```

### Rule Engine Implementation
```python
class BusinessRuleEngine:
    """Configurable rule engine for expense categorization."""

    def __init__(self, config_path: str):
        self.rules = self._load_rules(config_path)
        self.rule_history: list[RuleApplication] = []

    def apply_rules(self, line_item: LineItem, context: ExpenseContext) -> RuleResult:
        """Apply business rules to categorize a line item."""
        matching_rules = self._find_matching_rules(line_item, context)
        best_rule = self._select_best_rule(matching_rules)
        result = self._apply_rule(best_rule, line_item)
        self._log_rule_application(line_item, best_rule, result)
        return result

    def validate_rules(self) -> list[ValidationError]:
        """Validate rule configuration for conflicts and errors."""
        pass
```

## Testing Requirements

### Unit Tests
- [ ] Rule loading and validation tests
- [ ] Pattern matching tests (exact, contains, regex)
- [ ] Priority resolution tests with conflicting rules
- [ ] Fallback rule application tests
- [ ] Rule application logging tests
- [ ] Configuration schema validation tests

### Integration Tests
- [ ] End-to-end rule application with real receipt data
- [ ] Marriott hotel bill processing with multiple rules
- [ ] Rule conflict resolution scenarios
- [ ] Performance tests with large rule sets (100+ rules)
- [ ] Hot-reload functionality tests

### Test Data Examples
```json
{
  "test_scenarios": [
    {
      "name": "Marriott Hotel Bill",
      "line_items": [
        {"description": "Room Charge", "amount": 175.00},
        {"description": "Restaurant Room Charge", "amount": 40.70}
      ],
      "expected_rules": ["hotel_accommodation", "restaurant_meals"],
      "expected_categories": ["Travel-Lodging", "Travel-Meals"],
      "expected_deductibility": [100, 50]
    }
  ]
}
```

## Dependencies
- **PRE-106: Enhanced Models** - Required for line item categorization fields
- JSON schema validation library
- Pattern matching utilities

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Rule engine processes complex receipts correctly
- [ ] Default Canadian tax rules configured and tested
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real-world scenarios
- [ ] Performance benchmarks meet requirements (<100ms per line item)
- [ ] Code review completed and approved
- [ ] Documentation includes rule configuration guide

## Validation Scenarios

### Scenario 1: Marriott Hotel Bill Processing
**Given** a hotel bill with room charges and restaurant charges
**When** processed through the rule engine
**Then**
- Room charges match "hotel_accommodation" rule → Travel-Lodging, 100% deductible
- Restaurant charges match "restaurant_meals" rule → Travel-Meals, 50% deductible
- Rules applied are logged for audit purposes

### Scenario 2: Ambiguous Line Item Resolution
**Given** a line item that matches multiple rules
**When** processed through the rule engine
**Then** the highest priority rule is applied and conflict is logged

### Scenario 3: Unknown Expense Handling
**Given** a line item that matches no specific rules
**When** processed through the rule engine
**Then** fallback rule is applied and item is flagged for manual review

### Scenario 4: Rule Configuration Update
**Given** updated business rules configuration
**When** rules are hot-reloaded
**Then** new rules are applied to subsequent expenses without system restart

## Risk Mitigation
- **Rule Conflicts:** Comprehensive validation and priority-based conflict resolution
- **Performance:** Efficient pattern matching algorithms, rule caching
- **Configuration Errors:** JSON schema validation, rule consistency checks
- **Business Logic Changes:** Version control for rule configurations, rollback capability

## Success Metrics
- Rule engine categorizes >95% of line items correctly without manual intervention
- Rule application time <100ms per line item for typical receipts
- Zero rule conflicts in default configuration
- Business users can modify rules without developer assistance
- System handles 10+ different business expense categories accurately
