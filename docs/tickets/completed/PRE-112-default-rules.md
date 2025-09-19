# PRE-112: Default Business Rules Configuration

**Type:** Story
**Priority:** Low
**Effort:** 2 Story Points
**Sprint:** User Experience Layer

## User Story
**As a** small business owner
**I want** the system to work out-of-the-box with sensible defaults for common Canadian business expenses
**So that** I can start processing receipts immediately without complex configuration

## Business Value
- **Problem:** Empty rule engine requires technical configuration before any expense processing
- **Impact:** Poor onboarding experience, requires developer knowledge to make system functional
- **Solution:** Pre-configured rules covering 90% of common small business expense scenarios

## Description
Create a comprehensive default business rules configuration that covers common Canadian small business expense scenarios including travel, office supplies, meals, equipment, and professional services. Rules should be CRA-compliant and provide excellent out-of-the-box categorization accuracy.

## Acceptance Criteria

### AC1: Comprehensive Rule Coverage
- [ ] Rules cover all major small business expense categories
- [ ] Travel expenses (accommodation, meals, transportation) properly categorized
- [ ] Office and operational expenses (supplies, utilities, software) handled
- [ ] Professional services (legal, accounting, consulting) categorized
- [ ] Equipment purchases with capital vs expense determination hints
- [ ] GST/HST and tax-related items properly identified

### AC2: Canadian Tax Compliance
- [ ] All rules comply with current CRA requirements
- [ ] Meal deductibility limited to 50% per ITA Section 67.1
- [ ] GST/HST Input Tax Credits properly identified and categorized
- [ ] Capital asset vs expense thresholds considered
- [ ] Foreign currency transaction handling included
- [ ] Travel expense deductibility rules implemented correctly

### AC3: Pattern Matching Excellence
- [ ] Rules use comprehensive keyword matching for accurate categorization
- [ ] Vendor pattern matching for common Canadian businesses
- [ ] Amount-based rules for capital vs expense determination
- [ ] Context-aware rules (hotel bills, restaurant receipts, etc.)
- [ ] Priority ordering prevents rule conflicts
- [ ] Fallback rules handle edge cases gracefully

### AC4: QuickBooks Account Mapping
- [ ] Rules map to standard QuickBooks Chart of Accounts
- [ ] Account names follow Canadian small business best practices
- [ ] Account hierarchy supports detailed reporting
- [ ] Multiple account options for different business types
- [ ] Standard expense account creation guidance included
- [ ] Integration with existing QB setups

### AC5: Documentation and Customization
- [ ] Complete documentation for each rule with examples
- [ ] Clear explanation of Canadian tax implications
- [ ] Customization guide for different business types
- [ ] Rule priority and conflict resolution documentation
- [ ] Examples of rule modifications for specific industries
- [ ] Migration guide from basic to advanced rule setups

## Technical Implementation

### Files to Create
- `config/business_rules.json` - Default rule configuration
- `config/business_rules.schema.json` - JSON schema validation
- `docs/business_rules_guide.md` - Configuration documentation
- `config/industry_templates/` - Industry-specific rule variations
- `tests/config/test_default_rules.py` - Rule validation tests

### Default Rules Structure
```json
{
  "version": "1.0",
  "description": "Default Canadian small business expense rules",
  "metadata": {
    "jurisdiction": "Canada",
    "tax_year": "2024",
    "cra_compliance": true,
    "last_updated": "2024-01-15"
  },
  "rules": [
    {
      "id": "hotel_accommodation",
      "priority": 100,
      "name": "Hotel Accommodation Charges",
      "description": "Room charges, accommodation fees at hotels, motels, B&Bs",
      "conditions": {
        "description_keywords": [
          "room charge", "accommodation", "hotel", "motel", "lodging",
          "suite", "resort fee", "destination fee", "tourism levy"
        ],
        "vendor_patterns": [
          "*hotel*", "*inn*", "*resort*", "*motel*", "*lodge*",
          "*marriott*", "*hilton*", "*fairmont*", "*best western*"
        ],
        "amount_range": {"min": 50.00, "max": 2000.00}
      },
      "actions": {
        "category": "Travel-Lodging",
        "deductibility_percentage": 100,
        "qb_account": "Travel - Lodging",
        "tax_treatment": "standard",
        "compliance_note": "100% deductible business travel accommodation",
        "confidence_boost": 0.15
      }
    },
    {
      "id": "business_meals",
      "priority": 90,
      "name": "Business Meal Expenses",
      "description": "Restaurant charges, meal expenses during business travel or client meetings",
      "conditions": {
        "description_keywords": [
          "restaurant", "meal", "dining", "food", "coffee", "lunch", "dinner",
          "breakfast", "catering", "room service", "bar", "beverage"
        ],
        "vendor_patterns": [
          "*restaurant*", "*cafe*", "*bistro*", "*grill*", "*pizza*",
          "*starbucks*", "*tim hortons*", "*mcdonald*"
        ],
        "exclude_keywords": ["grocery", "supermarket", "convenience"],
        "amount_range": {"min": 5.00, "max": 500.00}
      },
      "actions": {
        "category": "Travel-Meals",
        "deductibility_percentage": 50,
        "qb_account": "Travel - Meals & Entertainment",
        "tax_treatment": "meals_limitation",
        "compliance_note": "CRA ITA Section 67.1 - 50% deductible limit applies",
        "confidence_boost": 0.10
      }
    },
    {
      "id": "office_supplies",
      "priority": 80,
      "name": "Office Supplies and Materials",
      "description": "General office supplies, stationery, consumables",
      "conditions": {
        "description_keywords": [
          "paper", "pen", "pencil", "stapler", "folder", "binder",
          "ink", "toner", "supplies", "stationery", "notebook"
        ],
        "vendor_patterns": [
          "*staples*", "*office depot*", "*costco*", "*walmart*",
          "*amazon*", "*best buy*"
        ],
        "amount_range": {"min": 1.00, "max": 500.00}
      },
      "actions": {
        "category": "Office Supplies",
        "deductibility_percentage": 100,
        "qb_account": "Office Supplies",
        "tax_treatment": "standard",
        "compliance_note": "100% deductible business supplies"
      }
    },
    {
      "id": "software_subscriptions",
      "priority": 85,
      "name": "Software and Subscriptions",
      "description": "Business software, SaaS subscriptions, digital services",
      "conditions": {
        "description_keywords": [
          "software", "subscription", "license", "saas", "cloud",
          "microsoft", "adobe", "quickbooks", "google workspace"
        ],
        "vendor_patterns": [
          "*microsoft*", "*adobe*", "*google*", "*intuit*",
          "*salesforce*", "*zoom*", "*slack*"
        ],
        "amount_range": {"min": 10.00, "max": 1000.00}
      },
      "actions": {
        "category": "Software & Technology",
        "deductibility_percentage": 100,
        "qb_account": "Software & Subscriptions",
        "tax_treatment": "standard",
        "compliance_note": "100% deductible business software expenses"
      }
    },
    {
      "id": "professional_services",
      "priority": 75,
      "name": "Professional Services",
      "description": "Legal, accounting, consulting, professional fees",
      "conditions": {
        "description_keywords": [
          "legal", "accounting", "consulting", "professional", "advisory",
          "audit", "tax preparation", "lawyer", "accountant"
        ],
        "vendor_patterns": [
          "*law*", "*legal*", "*accounting*", "*tax*", "*consulting*",
          "*cpa*", "*chartered*"
        ],
        "amount_range": {"min": 100.00, "max": 10000.00}
      },
      "actions": {
        "category": "Professional Services",
        "deductibility_percentage": 100,
        "qb_account": "Professional Services",
        "tax_treatment": "standard",
        "compliance_note": "100% deductible professional services"
      }
    },
    {
      "id": "gst_hst_tax",
      "priority": 95,
      "name": "GST/HST and Sales Tax",
      "description": "Goods and Services Tax, Harmonized Sales Tax",
      "conditions": {
        "description_keywords": [
          "gst", "hst", "tax", "sales tax", "goods and services tax",
          "harmonized sales tax"
        ],
        "amount_range": {"min": 0.50, "max": 1000.00}
      },
      "actions": {
        "category": "Tax-GST",
        "deductibility_percentage": 100,
        "qb_account": "GST/HST Paid on Purchases",
        "tax_treatment": "input_tax_credit",
        "compliance_note": "Input Tax Credit eligible - 100% recoverable",
        "confidence_boost": 0.20
      }
    },
    {
      "id": "equipment_capital",
      "priority": 70,
      "name": "Equipment and Capital Items",
      "description": "Computer equipment, furniture, tools over capital threshold",
      "conditions": {
        "description_keywords": [
          "computer", "laptop", "monitor", "printer", "desk", "chair",
          "equipment", "furniture", "tool", "machine"
        ],
        "vendor_patterns": [
          "*best buy*", "*staples*", "*amazon*", "*dell*", "*hp*",
          "*apple*", "*lenovo*"
        ],
        "amount_range": {"min": 500.00, "max": 50000.00}
      },
      "actions": {
        "category": "Equipment & Furniture",
        "deductibility_percentage": 100,
        "qb_account": "Equipment",
        "tax_treatment": "capital",
        "compliance_note": "May require capitalization - consult CCA rules",
        "requires_review": true
      }
    }
  ],
  "fallback_rules": {
    "unknown_expense": {
      "category": "General Business Expense",
      "deductibility_percentage": 100,
      "qb_account": "Other Business Expenses",
      "tax_treatment": "standard",
      "requires_manual_review": true,
      "compliance_note": "Unmatched expense - verify business purpose"
    }
  },
  "industry_variations": {
    "consulting": {
      "additional_rules": ["client_entertainment", "training_courses"],
      "modified_priorities": {"professional_services": 95}
    },
    "retail": {
      "additional_rules": ["inventory_purchases", "pos_systems"],
      "modified_priorities": {"office_supplies": 95}
    }
  }
}
```

### Industry Template Examples
```json
// config/industry_templates/consulting.json
{
  "extends": "business_rules.json",
  "industry": "consulting",
  "additional_rules": [
    {
      "id": "client_entertainment",
      "priority": 88,
      "name": "Client Entertainment",
      "conditions": {
        "description_keywords": ["entertainment", "client meeting", "business development"],
        "amount_range": {"min": 25.00, "max": 300.00}
      },
      "actions": {
        "category": "Client Entertainment",
        "deductibility_percentage": 50,
        "qb_account": "Meals & Entertainment",
        "tax_treatment": "meals_limitation"
      }
    }
  ]
}
```

## Testing Requirements

### Unit Tests
- [ ] Rule loading and validation tests
- [ ] Pattern matching accuracy tests for each rule
- [ ] Priority resolution tests with overlapping rules
- [ ] Canadian tax compliance validation tests
- [ ] Industry template loading tests
- [ ] Fallback rule application tests

### Integration Tests
- [ ] End-to-end rule application with real receipt data
- [ ] Marriott hotel bill categorization accuracy
- [ ] Office supply receipt processing
- [ ] Restaurant receipt meal limitation application
- [ ] Equipment purchase capital vs expense determination
- [ ] Multi-category receipt processing accuracy

### Coverage Tests
```python
# Test scenarios for rule coverage
TEST_RECEIPTS = {
    "marriott_hotel": {
        "expected_categories": ["Travel-Lodging", "Travel-Meals", "Tax-GST"],
        "expected_deductibility": [100, 50, 100]
    },
    "office_depot": {
        "expected_categories": ["Office Supplies", "Tax-GST"],
        "expected_deductibility": [100, 100]
    },
    "restaurant_meal": {
        "expected_categories": ["Travel-Meals", "Tax-GST"],
        "expected_deductibility": [50, 100]
    },
    "dell_computer": {
        "expected_categories": ["Equipment & Furniture", "Tax-GST"],
        "expected_deductibility": [100, 100],
        "requires_review": [true, false]
    }
}
```

## Dependencies
- **PRE-107: Business Rules Engine** - Required for rule application infrastructure

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Rules provide >90% categorization accuracy for common expenses
- [ ] Complete documentation with examples and customization guide
- [ ] All rules validated for CRA tax compliance
- [ ] Unit tests pass with 100% rule coverage
- [ ] Integration tests validate real-world scenarios
- [ ] Industry template examples created and tested
- [ ] Code review completed and approved

## Validation Scenarios

### Scenario 1: Out-of-Box Hotel Bill Processing
**Given** a new user with default rules configuration
**When** they upload a Marriott hotel bill
**Then** all line items are categorized correctly without any configuration

### Scenario 2: Common Business Expense Coverage
**Given** typical small business receipts (office, meals, professional services)
**When** processed with default rules
**Then** >90% of expenses are categorized accurately without manual intervention

### Scenario 3: Canadian Tax Compliance
**Given** various expense types processed with default rules
**When** tax calculations are performed
**Then** all deductibility percentages and treatments comply with current CRA rules

### Scenario 4: Rule Conflict Resolution
**Given** a receipt that could match multiple rules
**When** processed through the default rule set
**Then** highest priority rule is applied consistently

## Risk Mitigation
- **Rule Accuracy:** Comprehensive testing with real-world receipts
- **Tax Compliance:** Regular review against current CRA guidelines
- **Business Variation:** Industry templates handle different business needs
- **Maintenance:** Version control and update procedures for rule changes

## Success Metrics
- >90% categorization accuracy on common business expenses
- <5% of receipts require manual review with default rules
- Zero tax compliance violations in default rule configuration
- New users can process receipts successfully within 5 minutes of setup
- Default rules cover 95%+ of typical small business expense scenarios
