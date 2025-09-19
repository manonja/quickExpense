# Entity-Aware Architecture: Scalable Tax Compliance System

## Progressive Enhancement Approach

Our system follows a **progressive enhancement strategy** - starting with a solid foundation for Canadian sole proprietors (T2125), then expanding to support corporations and partnerships. This approach allows us to ship working code quickly while learning the domain complexity.

## Current State: Sole Proprietorship (T2125) Focus

### Entity Type: `sole_proprietorship`
- **Tax Form:** T2125 (Statement of Business or Professional Activities)
- **Filing:** Filed with personal T1 tax return
- **Key Features:**
  - Meals & entertainment 50% limitation (ITA Section 67.1)
  - Home office expense restrictions (ITA Section 18(12))
  - Complete T2125 line item mapping
  - Provincial GST/HST/PST/QST calculations
  - Input Tax Credit eligibility

### T2125 Line Item Intelligence

```python
class T2125LineItem(str, Enum):
    """Official CRA T2125 form line items."""

    ADVERTISING = "8521"           # Advertising
    MEALS_ENTERTAINMENT = "8523"   # Meals (50% deductible)
    OFFICE_SUPPLIES = "8811"       # Office expenses
    PROFESSIONAL_FEES = "8860"     # Legal, accounting
    TRAVEL = "8890"                # Travel expenses
    VEHICLE_EXPENSES = "9281"      # Motor vehicle
    HOME_OFFICE = "9945"           # Business-use-of-home

    @property
    def deductibility_percentage(self) -> float:
        """Default deductibility for line item."""
        return {
            "8523": 50.0,  # Meals limitation
            "9945": "variable"  # Home office (depends on use %)
        }.get(self.value, 100.0)
```

### Entity-Aware Business Rules

```python
def get_tax_treatment(entity_type: str, expense_category: str) -> TaxTreatment:
    """Get tax treatment based on entity type."""

    if entity_type == "sole_proprietorship":
        return T2125TaxTreatment(
            form_line=T2125LineItem.from_category(expense_category),
            deductibility=get_sole_prop_deductibility(expense_category),
            ita_reference=get_ita_section(expense_category)
        )
    elif entity_type == "corporation":
        # Future implementation
        return T2TaxTreatment(...)
    elif entity_type == "partnership":
        # Future implementation
        return T5013TaxTreatment(...)
```

## Future Scalability: Multi-Entity Support

### Phase 2: Corporation Support (`corporation`)
- **Tax Form:** T2 Corporation Income Tax Return
- **Key Differences:**
  - No meals limitation (100% deductible if ordinary business expense)
  - Different capital cost allowance rules
  - Small business deduction considerations
  - Active business income vs investment income

### Phase 3: Partnership Support (`partnership`)
- **Tax Form:** T5013 Partnership Information Return
- **Key Differences:**
  - Flow-through taxation to partners
  - Allocation of income/expenses by partnership percentage
  - No entity-level tax (flows to partners' personal/corporate returns)

## System Intelligence Evolution

### Current: Single Agent with Basic Rules
```python
class SoleProprietorshipAgent:
    """Specialized agent for sole proprietor tax rules."""

    def categorize_expense(self, receipt_data: dict) -> ExpenseCategory:
        # Apply T2125-specific rules
        # Consider meals limitation
        # Map to T2125 line items
        pass
```

### Future: Multi-Agent Consensus System
```python
class TaxComplianceOrchestrator:
    """Orchestrate multiple specialized agents."""

    def __init__(self):
        self.agents = {
            "sole_proprietorship": SoleProprietorshipAgent(),
            "corporation": CorporationAgent(),         # Future
            "partnership": PartnershipAgent(),         # Future
            "tax_specialist": TaxSpecialistAgent(),    # Future
            "compliance_officer": ComplianceAgent(),   # Future
            "auditor": AuditAgent()                    # Future
        }

    async def get_consensus(self, receipt_data: dict, entity_type: str) -> Consensus:
        """Get multi-agent consensus on expense treatment."""

        # Primary agent based on entity type
        primary_result = await self.agents[entity_type].analyze(receipt_data)

        # Cross-validation from specialists
        tax_validation = await self.agents["tax_specialist"].validate(primary_result)
        compliance_check = await self.agents["compliance_officer"].check(primary_result)
        audit_review = await self.agents["auditor"].assess_risk(primary_result)

        # Consensus algorithm
        return self._reach_consensus([
            primary_result, tax_validation, compliance_check, audit_review
        ])
```

## Configuration-Driven Entity Awareness

### User Configuration
```json
{
  "business": {
    "entity_type": "sole_proprietorship",
    "tax_form": "T2125",
    "province": "BC",
    "gst_number": "123456789RT0001",
    "business_type": "consulting"
  }
}
```

### Automatic Form Selection
```python
def get_tax_form(entity_type: str) -> str:
    """Auto-select tax form based on entity type."""
    return {
        "sole_proprietorship": "T2125",
        "corporation": "T2",
        "partnership": "T5013"
    }[entity_type]
```

## CLI Output Evolution

### Current: T2125-Aware Output
```bash
$ quickexpense upload receipt.pdf

=== Business Rules Categorization ===
📄 Restaurant Meal
   Entity Type: Sole Proprietorship
   Tax Form: T2125
   Form Line: 8523 (Meals and entertainment)
   Deductible: 50% ($25.00 of $50.00)
   ITA Reference: Section 67.1
   ✅ Matched Rule
```

### Future: Multi-Entity Support
```bash
$ quickexpense upload receipt.pdf --entity-type corporation

=== Business Rules Categorization ===
📄 Restaurant Meal
   Entity Type: Corporation
   Tax Form: T2
   Schedule: 125 (Business expenses)
   Deductible: 100% ($50.00)
   Note: Ordinary business expense
   ✅ Multi-Agent Consensus (95% confidence)
```

## Audit Trail Evolution

### Current: T2125 Compliance
```json
{
  "event_type": "expense_categorization",
  "entity_type": "sole_proprietorship",
  "tax_form": "T2125",
  "form_line_item": "8523",
  "deductibility_percentage": 50,
  "ita_reference": "67.1",
  "compliance_status": "compliant"
}
```

### Future: Multi-Entity Compliance
```json
{
  "event_type": "multi_agent_consensus",
  "entity_type": "corporation",
  "tax_form": "T2",
  "agent_results": [
    {"agent": "corporation_specialist", "confidence": 0.95},
    {"agent": "tax_specialist", "confidence": 0.92},
    {"agent": "compliance_officer", "confidence": 0.98}
  ],
  "consensus_confidence": 0.95,
  "compliance_frameworks": ["CRA", "Provincial"]
}
```

## Business Rules Scalability

### Entity-Specific Rule Files
```
config/business_rules/
├── sole_proprietorship.json     # Current T2125 rules
├── corporation.json             # Future T2 rules
├── partnership.json             # Future T5013 rules
└── common.json                  # Cross-entity rules
```

### Rule Selection Logic
```python
def load_business_rules(entity_type: str) -> BusinessRulesEngine:
    """Load entity-specific business rules."""

    rules = []

    # Load common rules (apply to all entities)
    rules.extend(load_rules("common.json"))

    # Load entity-specific rules
    entity_rules_file = f"{entity_type}.json"
    rules.extend(load_rules(entity_rules_file))

    return BusinessRulesEngine(rules, entity_type)
```

## Migration Strategy

### Phase 1: Sole Proprietorship Excellence
1. Perfect T2125 compliance
2. Complete provincial tax support
3. Professional audit trails
4. Entity-aware foundation

### Phase 2: Corporation Support
1. Add T2 form models
2. Corporation-specific business rules
3. Multi-agent validation
4. Capital cost allowance support

### Phase 3: Partnership Support
1. Add T5013 form models
2. Flow-through taxation logic
3. Partner allocation algorithms
4. Cross-entity reconciliation

### Phase 4: Advanced Intelligence
1. Multi-entity consolidation
2. Transfer pricing compliance
3. International tax considerations
4. AI-powered tax optimization

## Success Metrics

### Phase 1 (Current):
- 100% T2125 line item accuracy
- Provincial tax compliance across Canada
- CRA audit readiness

### Future Phases:
- Support 3+ entity types seamlessly
- Multi-agent consensus >95% accuracy
- Cross-entity tax optimization
- Enterprise-grade compliance reporting

This architecture ensures our excellent sole proprietorship foundation becomes the launching pad for comprehensive Canadian business tax compliance across all entity types.
