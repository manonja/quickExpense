# PRE-111: Context-Aware AI Extraction

**Type:** Story
**Priority:** Medium
**Effort:** 4 Story Points
**Sprint:** Processing Engine Layer

## User Story
**As a** small business owner
**I want** AI extraction to understand business context and categorize line items accurately
**So that** complex receipts like hotel bills are processed correctly with minimal manual intervention

## Business Value
- **Problem:** Current AI extraction treats all receipts generically, missing business-specific categorization opportunities
- **Impact:** Requires manual review and correction of categorized expenses, especially for complex receipts
- **Solution:** Context-aware AI that understands business types, tax rules, and categorization patterns

## Description
Enhance the Gemini AI service to be context-aware by injecting business knowledge, expense categorization hints, and domain-specific prompts. The system should provide line-item level categorization suggestions and confidence scoring to work seamlessly with the business rules engine.

## Acceptance Criteria

### AC1: Business Context Integration
- [ ] AI prompts include business context (small business, Canadian tax rules)
- [ ] Extraction prompts include common expense categories and patterns
- [ ] AI understands deductibility concepts (100% vs 50% for meals)
- [ ] System provides category suggestions for each line item
- [ ] AI considers vendor type context (hotel, restaurant, office supply)
- [ ] Extraction includes confidence scoring for categorization suggestions

### AC2: Enhanced Line-Item Extraction
- [ ] AI extracts line items with suggested categories
- [ ] AI identifies potential tax treatments (standard, meals limitation, capital)
- [ ] AI provides confidence scores for each categorization
- [ ] AI flags ambiguous items requiring manual review
- [ ] AI maintains existing receipt data extraction quality
- [ ] AI handles various receipt formats and layouts consistently

### AC3: Domain-Specific Prompts
- [ ] Hotel bill prompts distinguish accommodation vs meal charges
- [ ] Restaurant prompts identify business meal context
- [ ] Office supply prompts categorize items appropriately
- [ ] Travel expense prompts identify transportation, lodging, meals
- [ ] Equipment purchase prompts distinguish capital vs expense items
- [ ] GST/HST prompts identify tax amounts for Input Tax Credits

### AC4: Validation and Quality Assurance
- [ ] AI extraction results validate against business rules
- [ ] System flags inconsistencies between AI suggestions and rules
- [ ] AI provides reasoning for categorization suggestions
- [ ] System learns from manual corrections (future enhancement hook)
- [ ] AI maintains high accuracy for monetary calculations
- [ ] System handles edge cases gracefully with appropriate confidence scores

### AC5: Integration with Business Rules
- [ ] AI suggestions map to business rule categories
- [ ] AI confidence scores inform rule application priority
- [ ] AI categorization works with rule engine validation
- [ ] System uses AI suggestions as input to rule matching
- [ ] AI supports rule override scenarios with explanations
- [ ] System provides feedback loop for rule effectiveness

## Technical Implementation

### Files to Modify
- `src/quickexpense/services/gemini.py` - Enhance existing Gemini service
- `src/quickexpense/models/receipt.py` - Add categorization fields
- `src/quickexpense/services/ai_prompt_builder.py` - New context-aware prompting
- `src/quickexpense/services/extraction_validator.py` - AI result validation
- `tests/services/test_context_aware_extraction.py` - Comprehensive tests

### Enhanced Gemini Service
```python
class ContextAwareGeminiService:
    """Enhanced Gemini service with business context awareness."""

    def __init__(
        self,
        settings: Settings,
        prompt_builder: AIPromptBuilder,
        validator: ExtractionValidator
    ):
        self.settings = settings
        self.prompt_builder = prompt_builder
        self.validator = validator
        self.model = self._configure_model()

    async def extract_receipt_with_context(
        self,
        image_base64: str,
        business_context: BusinessContext,
        additional_context: str | None = None
    ) -> ContextualReceiptExtraction:
        """Extract receipt data with business context awareness."""

        start_time = time.time()

        try:
            # 1. Build context-aware prompt
            prompt = self.prompt_builder.build_context_prompt(
                business_context, additional_context
            )

            # 2. Process image with enhanced prompt
            image = self._decode_image(image_base64)
            response = self.model.generate_content([prompt, image])

            if not response.text:
                raise ExtractionError("No response from Gemini model")

            # 3. Parse enhanced response
            extraction_data = self._parse_contextual_response(response.text)

            # 4. Validate extraction quality
            validation_results = await self.validator.validate_extraction(
                extraction_data, business_context
            )

            # 5. Create contextual receipt extraction
            contextual_receipt = ContextualReceiptExtraction(
                **extraction_data,
                business_context=business_context,
                validation_results=validation_results,
                processing_time=time.time() - start_time,
                ai_model_version=self.settings.gemini_model
            )

            return contextual_receipt

        except Exception as e:
            logger.error(f"Contextual extraction failed: {e}")
            raise ExtractionError(f"AI extraction failed: {e}") from e

class AIPromptBuilder:
    """Builds context-aware prompts for AI extraction."""

    def build_context_prompt(
        self,
        business_context: BusinessContext,
        additional_context: str | None = None
    ) -> str:
        """Build context-aware extraction prompt."""

        base_prompt = self._get_base_extraction_prompt()
        context_prompt = self._build_business_context(business_context)
        categorization_prompt = self._build_categorization_guidance()

        full_prompt = f"""
{base_prompt}

{context_prompt}

{categorization_prompt}

IMPORTANT: For each line item, suggest a category and provide confidence score (0-1).

Example categorization for hotel bills:
- Room charges, accommodation fees → "Travel-Lodging" (100% deductible)
- Restaurant charges, meal charges → "Travel-Meals" (50% deductible in Canada)
- GST, HST, taxes → "Tax-GST" (Input Tax Credit eligible)
- Tourism levies, hotel fees → "Travel-Lodging" (100% deductible)

Return JSON with this enhanced schema:
{{
    "vendor_name": "string",
    "transaction_date": "YYYY-MM-DD",
    "line_items": [
        {{
            "description": "string",
            "amount": "number",
            "suggested_category": "string",
            "confidence_score": "number 0-1",
            "deductibility_hint": "100|50|0",
            "tax_treatment_hint": "standard|meals_limitation|input_tax_credit|capital"
        }}
    ],
    "total_amount": "number",
    "currency": "string",
    "categorization_confidence": "number 0-1",
    "receipt_type": "hotel|restaurant|office|equipment|other"
}}
        """

        if additional_context:
            full_prompt += f"\n\nAdditional context: {additional_context}"

        return full_prompt

    def _build_business_context(self, context: BusinessContext) -> str:
        """Build business-specific context for prompts."""

        context_parts = [
            f"Business type: {context.business_type}",
            f"Tax jurisdiction: {context.tax_jurisdiction}",
            f"Accounting period: {context.accounting_period}"
        ]

        if context.tax_jurisdiction == "Canada":
            context_parts.append(
                "Canadian tax rules apply:\n"
                "- Business meals: 50% deductible (ITA Section 67.1)\n"
                "- Travel accommodation: 100% deductible\n"
                "- GST/HST: Input Tax Credits available\n"
                "- Equipment: May be capital vs expense"
            )

        return "\n".join(context_parts)

    def _build_categorization_guidance(self) -> str:
        """Build categorization guidance for AI."""

        return """
CATEGORIZATION GUIDELINES:

Travel & Transportation:
- "Travel-Lodging": Room charges, hotel fees, accommodation
- "Travel-Meals": Restaurant, meal charges, dining
- "Travel-Transport": Flights, trains, taxis, car rental

Office & Operations:
- "Office Supplies": Paper, pens, software, subscriptions
- "Equipment": Computers, furniture, tools (consider capital vs expense)
- "Professional Services": Legal, accounting, consulting

Tax & Compliance:
- "Tax-GST": GST, HST, sales tax (Input Tax Credit eligible)
- "Tax-Other": Other taxes and government fees

General:
- "General Business": Miscellaneous business expenses
- "Utilities": Internet, phone, electricity for business use
"""

class ContextualReceiptExtraction(ExtractedReceipt):
    """Enhanced receipt extraction with categorization."""

    business_context: BusinessContext
    validation_results: ValidationResults
    ai_model_version: str
    categorization_confidence: float = Field(ge=0, le=1)
    receipt_type: str | None = None
    suggested_business_rules: list[str] = Field(default_factory=list)
```

### Models
```python
class BusinessContext(BaseModel):
    """Business context for AI extraction."""
    business_type: str = "small_business"
    tax_jurisdiction: str = "Canada"
    accounting_period: str = "monthly"
    primary_categories: list[str] = Field(default_factory=list)
    custom_rules: dict[str, Any] = Field(default_factory=dict)

class CategorizedLineItem(BaseModel):
    """Line item with AI categorization suggestions."""
    description: str
    amount: Decimal
    quantity: Decimal = Field(default=Decimal('1'))
    suggested_category: str
    confidence_score: float = Field(ge=0, le=1)
    deductibility_hint: int = Field(ge=0, le=100)
    tax_treatment_hint: str = "standard"
    reasoning: str | None = None

class ValidationResults(BaseModel):
    """Validation results for AI extraction."""
    total_validation: bool
    line_item_validation: bool
    categorization_quality: float = Field(ge=0, le=1)
    identified_issues: list[str] = Field(default_factory=list)
    suggested_corrections: list[str] = Field(default_factory=list)
```

## Testing Requirements

### Unit Tests
- [ ] Context-aware prompt building tests
- [ ] Categorization suggestion validation tests
- [ ] Confidence score accuracy tests
- [ ] Business context integration tests
- [ ] Enhanced extraction parsing tests
- [ ] Validation logic tests

### Integration Tests
- [ ] End-to-end Marriott hotel bill extraction with categorization
- [ ] Restaurant receipt extraction with meal context
- [ ] Office supply receipt extraction and categorization
- [ ] Equipment purchase extraction with capital/expense hints
- [ ] Multi-vendor receipt categorization accuracy tests
- [ ] Performance tests with context-aware processing

### Test Scenarios
```python
# Marriott Hotel Bill AI Extraction Test
{
    "input": {
        "receipt_type": "hotel_bill",
        "business_context": {
            "business_type": "consulting",
            "tax_jurisdiction": "Canada"
        }
    },
    "expected_extraction": {
        "line_items": [
            {
                "description": "Room Charge",
                "amount": 175.00,
                "suggested_category": "Travel-Lodging",
                "confidence_score": 0.95,
                "deductibility_hint": 100,
                "tax_treatment_hint": "standard"
            },
            {
                "description": "Restaurant Room Charge",
                "amount": 40.70,
                "suggested_category": "Travel-Meals",
                "confidence_score": 0.88,
                "deductibility_hint": 50,
                "tax_treatment_hint": "meals_limitation"
            }
        ],
        "receipt_type": "hotel",
        "categorization_confidence": 0.92
    }
}
```

## Dependencies
- **PRE-108: File Processing** - Required for enhanced image processing
- Existing Gemini service infrastructure

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] AI provides accurate categorization suggestions for complex receipts
- [ ] Context-aware prompts improve categorization accuracy by >15%
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real-world categorization scenarios
- [ ] Performance impact is minimal (<500ms additional processing)
- [ ] Code review completed and approved
- [ ] Documentation includes prompt engineering guide

## Validation Scenarios

### Scenario 1: Marriott Hotel Bill Context Extraction
**Given** a Marriott hotel bill image with business context
**When** processed through context-aware AI
**Then**
- Room charges suggested as "Travel-Lodging" with high confidence
- Restaurant charges suggested as "Travel-Meals" with deductibility hint 50%
- GST identified as "Tax-GST" with Input Tax Credit treatment
- Overall categorization confidence >90%

### Scenario 2: Ambiguous Receipt Handling
**Given** a receipt with unclear line items
**When** processed through context-aware AI
**Then** low confidence scores flag items for manual review

### Scenario 3: Business Context Variation
**Given** same receipt processed with different business contexts
**When** extraction runs with each context
**Then** categorization suggestions adapt appropriately to business type

### Scenario 4: Performance with Context
**Given** typical receipt processing load
**When** context-aware extraction is enabled
**Then** processing time increases by <20% vs basic extraction

## Risk Mitigation
- **AI Accuracy:** Comprehensive validation layer to catch incorrect categorizations
- **Performance:** Optimize prompts for efficiency while maintaining accuracy
- **Context Complexity:** Start with essential context, expand gradually
- **Integration:** Ensure seamless integration with existing business rules engine

## Success Metrics
- Categorization accuracy improves to >90% for common business expenses
- Manual review required for <10% of processed receipts
- Context-aware extraction processing time <3 seconds per receipt
- Confidence scores correlate with actual categorization accuracy >85%
- Zero degradation in existing extraction quality (amounts, dates, vendors)
