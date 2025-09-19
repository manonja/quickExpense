# PRE-120: Enhanced CLI Output with Business Intelligence

**Type:** Enhancement
**Priority:** Medium (User Experience)
**Effort:** 2 Story Points
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** sole proprietor managing business expenses throughout the year
**I want** rich CLI output that provides insights into my spending patterns and tax optimization opportunities
**So that** I can make informed business decisions and maximize my tax deductions

## Business Value
- **Problem:** Current CLI output is functional but lacks business insights and spending analysis
- **Impact:** Missed tax optimization opportunities, poor spending visibility, manual analysis required
- **Solution:** Intelligent CLI output with spending summaries, tax insights, and actionable recommendations

## Description
Enhance the CLI interface to provide comprehensive business intelligence including spending summaries by category and time period, tax optimization suggestions, compliance warnings, and actionable recommendations. The system should help sole proprietors understand their spending patterns and optimize their tax strategy.

## Business Intelligence Requirements
**User Insights Needed:**
- Monthly/quarterly spending by category
- Tax deductibility analysis and optimization
- Compliance warnings and audit risk indicators
- Spending trend analysis and patterns
- Category-specific insights (meals limitation tracking)
- Provincial tax optimization opportunities

## Acceptance Criteria

### AC1: Enhanced Receipt Processing Output
- [ ] Add spending context to individual receipt output
- [ ] Show category totals and percentages
- [ ] Include tax optimization suggestions
- [ ] Display compliance warnings for potential issues
- [ ] Provide year-to-date context for current receipt
- [ ] Add confidence indicators for AI decisions

### AC2: Spending Summary Commands
- [ ] Implement `quickexpense summary` with time period options
- [ ] Support monthly, quarterly, and yearly summaries
- [ ] Break down spending by expense categories
- [ ] Show deductibility analysis by category
- [ ] Include provincial tax impact analysis
- [ ] Generate exportable reports (PDF, CSV)

### AC3: Tax Optimization Insights
- [ ] Track meals and entertainment 50% limitation progress
- [ ] Identify potential equipment depreciation opportunities
- [ ] Suggest timing optimizations for large purchases
- [ ] Highlight missing expense categories for tax planning
- [ ] Provide Input Tax Credit optimization suggestions
- [ ] Alert on unusual spending patterns requiring documentation

### AC4: Compliance and Audit Preparation
- [ ] Flag receipts missing required information
- [ ] Identify audit risk indicators (high amounts, unusual patterns)
- [ ] Suggest documentation improvements
- [ ] Track receipt retention compliance
- [ ] Generate audit-ready expense summaries
- [ ] Provide CRA compliance checklists

### AC5: Interactive Insights and Recommendations
- [ ] Contextual recommendations based on business type
- [ ] Seasonal spending pattern analysis
- [ ] Cross-provincial tax optimization suggestions
- [ ] Equipment vs expense decision support
- [ ] Business growth insights from spending trends

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/services/business_intelligence.py` - New BI service
- `src/quickexpense/services/spending_analyzer.py` - Spending analysis
- `src/quickexpense/services/tax_optimizer.py` - Tax optimization insights
- `src/quickexpense/cli.py` - Enhanced commands and output
- `tests/services/test_business_intelligence.py` - Comprehensive tests

### BusinessIntelligenceService
```python
class BusinessIntelligenceService:
    """Generate business insights and recommendations."""

    def __init__(
        self,
        spending_analyzer: SpendingAnalyzer,
        tax_optimizer: TaxOptimizer,
        compliance_checker: ComplianceChecker
    ):
        self.spending_analyzer = spending_analyzer
        self.tax_optimizer = tax_optimizer
        self.compliance_checker = compliance_checker

    async def generate_receipt_insights(
        self,
        processed_receipt: ProcessedReceipt,
        user_context: UserContext
    ) -> ReceiptInsights:
        """Generate insights for individual receipt processing."""

        # Analyze spending context
        spending_context = await self.spending_analyzer.analyze_receipt_context(
            processed_receipt, user_context
        )

        # Generate tax optimization suggestions
        tax_suggestions = await self.tax_optimizer.analyze_receipt(
            processed_receipt, user_context
        )

        # Check compliance issues
        compliance_warnings = await self.compliance_checker.check_receipt(
            processed_receipt
        )

        # Generate contextual recommendations
        recommendations = await self._generate_contextual_recommendations(
            processed_receipt, spending_context, user_context
        )

        return ReceiptInsights(
            spending_context=spending_context,
            tax_suggestions=tax_suggestions,
            compliance_warnings=compliance_warnings,
            recommendations=recommendations,
            year_to_date_impact=spending_context.ytd_impact
        )

    async def generate_spending_summary(
        self,
        period: TimePeriod,
        user_context: UserContext
    ) -> SpendingSummary:
        """Generate comprehensive spending summary."""

        # Analyze spending patterns
        spending_analysis = await self.spending_analyzer.analyze_period(
            period, user_context
        )

        # Generate tax optimization insights
        tax_optimization = await self.tax_optimizer.analyze_period(
            period, user_context
        )

        # Identify trends and patterns
        trends = await self.spending_analyzer.identify_trends(
            period, user_context
        )

        # Generate recommendations
        recommendations = await self._generate_period_recommendations(
            spending_analysis, tax_optimization, trends
        )

        return SpendingSummary(
            period=period,
            spending_analysis=spending_analysis,
            tax_optimization=tax_optimization,
            trends=trends,
            recommendations=recommendations
        )

class SpendingAnalyzer:
    """Analyze spending patterns and trends."""

    async def analyze_receipt_context(
        self,
        receipt: ProcessedReceipt,
        user_context: UserContext
    ) -> SpendingContext:
        """Analyze receipt in context of user's spending."""

        # Get historical data for comparison
        historical_data = await self._get_historical_spending(user_context)

        # Calculate category context
        category_context = self._analyze_category_spending(
            receipt.categorized_items, historical_data
        )

        # Determine if unusual amounts or patterns
        anomalies = self._detect_spending_anomalies(receipt, historical_data)

        # Calculate year-to-date impact
        ytd_impact = self._calculate_ytd_impact(receipt, historical_data)

        return SpendingContext(
            receipt_total=receipt.total_amount,
            category_breakdown=category_context,
            anomalies=anomalies,
            ytd_impact=ytd_impact,
            comparative_analysis=self._generate_comparative_analysis(
                receipt, historical_data
            )
        )

    async def analyze_period(
        self,
        period: TimePeriod,
        user_context: UserContext
    ) -> PeriodSpendingAnalysis:
        """Analyze spending for specific time period."""

        expenses = await self._get_expenses_for_period(period, user_context)

        # Category breakdown
        category_totals = self._calculate_category_totals(expenses)

        # Deductibility analysis
        deductibility_analysis = self._analyze_deductibility(expenses)

        # Provincial tax analysis
        provincial_analysis = self._analyze_provincial_impact(expenses)

        # Monthly/quarterly patterns
        temporal_patterns = self._analyze_temporal_patterns(expenses, period)

        return PeriodSpendingAnalysis(
            period=period,
            total_expenses=sum(e.total_amount for e in expenses),
            category_totals=category_totals,
            deductibility_analysis=deductibility_analysis,
            provincial_analysis=provincial_analysis,
            temporal_patterns=temporal_patterns
        )

class TaxOptimizer:
    """Generate tax optimization insights and suggestions."""

    async def analyze_receipt(
        self,
        receipt: ProcessedReceipt,
        user_context: UserContext
    ) -> TaxOptimizationSuggestions:
        """Generate tax optimization suggestions for receipt."""

        suggestions = []

        # Meals limitation tracking
        if self._has_meal_expenses(receipt):
            meals_suggestion = await self._analyze_meals_limitation(
                receipt, user_context
            )
            if meals_suggestion:
                suggestions.append(meals_suggestion)

        # Equipment vs expense analysis
        if self._has_equipment_purchases(receipt):
            equipment_suggestion = await self._analyze_equipment_treatment(
                receipt, user_context
            )
            if equipment_suggestion:
                suggestions.append(equipment_suggestion)

        # Provincial tax optimization
        provincial_suggestion = await self._analyze_provincial_optimization(
            receipt, user_context
        )
        if provincial_suggestion:
            suggestions.append(provincial_suggestion)

        return TaxOptimizationSuggestions(
            suggestions=suggestions,
            potential_savings=self._calculate_potential_savings(suggestions),
            compliance_notes=self._generate_compliance_notes(receipt)
        )

    async def _analyze_meals_limitation(
        self,
        receipt: ProcessedReceipt,
        user_context: UserContext
    ) -> TaxSuggestion | None:
        """Analyze meals and entertainment limitation impact."""

        ytd_meals = await self._get_ytd_meals_total(user_context)
        current_meals = sum(
            item.amount for item in receipt.categorized_items
            if item.category == "Travel-Meals"
        )

        # 50% limitation analysis
        deductible_amount = current_meals * 0.5
        limitation_cost = current_meals - deductible_amount

        if limitation_cost > 0:
            return TaxSuggestion(
                type="meals_limitation",
                title="Meals & Entertainment 50% Limitation",
                description=f"This receipt includes ${current_meals:.2f} in meals. "
                           f"Only ${deductible_amount:.2f} (50%) is tax deductible per CRA rules.",
                potential_impact=limitation_cost,
                action_items=[
                    "Ensure business purpose is documented",
                    "Consider timing of large entertainment expenses",
                    f"YTD meals total: ${ytd_meals + current_meals:.2f}"
                ]
            )

        return None
```

### Enhanced CLI Output
```python
class EnhancedCLIFormatter:
    """Rich CLI output with business intelligence."""

    def format_receipt_with_insights(
        self,
        receipt_result: ProcessingResult,
        insights: ReceiptInsights
    ) -> str:
        """Format receipt output with business insights."""

        output = []

        # Standard receipt output (existing)
        output.extend(self._format_standard_receipt_output(receipt_result))

        # Business insights section
        output.append("\n📊 Business Insights")
        output.append("=" * 50)

        # Spending context
        if insights.spending_context.anomalies:
            output.append("\n⚠️  Notable Patterns:")
            for anomaly in insights.spending_context.anomalies:
                output.append(f"  • {anomaly.description}")

        # Tax optimization suggestions
        if insights.tax_suggestions.suggestions:
            output.append("\n💡 Tax Optimization:")
            for suggestion in insights.tax_suggestions.suggestions:
                output.append(f"  • {suggestion.title}")
                output.append(f"    {suggestion.description}")
                if suggestion.action_items:
                    for action in suggestion.action_items:
                        output.append(f"    → {action}")

        # Compliance warnings
        if insights.compliance_warnings:
            output.append("\n⚠️  Compliance Notes:")
            for warning in insights.compliance_warnings:
                output.append(f"  • {warning.message}")

        # Year-to-date context
        if insights.year_to_date_impact:
            ytd = insights.year_to_date_impact
            output.append(f"\n📈 Year-to-Date Impact:")
            output.append(f"  • Total YTD Expenses: ${ytd.total_expenses:.2f}")
            output.append(f"  • This Receipt: ${receipt_result.total_amount:.2f} "
                         f"({ytd.percentage_of_total:.1f}% of YTD)")
            output.append(f"  • Top Category: {ytd.top_category} "
                         f"(${ytd.top_category_amount:.2f})")

        return "\n".join(output)

    def format_spending_summary(
        self,
        summary: SpendingSummary
    ) -> str:
        """Format comprehensive spending summary."""

        output = []

        # Header
        period_str = f"{summary.period.start_date} to {summary.period.end_date}"
        output.append(f"\n📊 Spending Summary: {period_str}")
        output.append("=" * 60)

        # Overall statistics
        analysis = summary.spending_analysis
        output.append(f"\n💰 Financial Overview:")
        output.append(f"  Total Expenses: ${analysis.total_expenses:.2f}")
        output.append(f"  Total Deductible: ${analysis.deductibility_analysis.total_deductible:.2f}")
        output.append(f"  Deductibility Rate: {analysis.deductibility_analysis.deductibility_percentage:.1f}%")

        # Category breakdown
        output.append(f"\n📋 Expenses by Category:")
        for category, amount in analysis.category_totals.items():
            percentage = (amount / analysis.total_expenses) * 100
            output.append(f"  • {category:<25} ${amount:>8.2f} ({percentage:>5.1f}%)")

        # Tax optimization insights
        if summary.tax_optimization.potential_savings:
            output.append(f"\n💡 Tax Optimization Opportunities:")
            for opportunity in summary.tax_optimization.potential_savings:
                output.append(f"  • {opportunity.description}")
                output.append(f"    Potential Savings: ${opportunity.amount:.2f}")

        # Trends and patterns
        if summary.trends:
            output.append(f"\n📈 Spending Trends:")
            for trend in summary.trends:
                output.append(f"  • {trend.description}")

        # Recommendations
        if summary.recommendations:
            output.append(f"\n🎯 Recommendations:")
            for recommendation in summary.recommendations:
                output.append(f"  • {recommendation.title}")
                output.append(f"    {recommendation.description}")

        return "\n".join(output)
```

### New CLI Commands
```bash
# Enhanced receipt processing (automatic insights)
quickexpense upload receipt.pdf
# Now includes spending context, tax suggestions, compliance warnings

# Spending summaries
quickexpense summary --month 2025-09
quickexpense summary --quarter Q3-2025
quickexpense summary --year 2025
quickexpense summary --last-30-days

# Specific analysis
quickexpense analyze meals --year 2025
quickexpense analyze provincial-taxes --quarter Q4-2025
quickexpense analyze equipment --year 2025

# Export reports
quickexpense summary --month 2025-09 --export summary.pdf
quickexpense summary --year 2025 --export yearly-report.csv

# Tax optimization insights
quickexpense optimize --category meals
quickexpense optimize --equipment-analysis
quickexpense optimize --provincial-comparison

# Entity-aware analysis (T2125 for sole proprietors)
quickexpense summary --entity-type sole_proprietorship --t2125-format
quickexpense analyze t2125 --year 2025
quickexpense optimize --meals-limitation --t2125
```

### Models
```python
class ReceiptInsights(BaseModel):
    """Business insights for individual receipt."""
    spending_context: SpendingContext
    tax_suggestions: TaxOptimizationSuggestions
    compliance_warnings: list[ComplianceWarning]
    recommendations: list[BusinessRecommendation]
    year_to_date_impact: YTDImpact | None = None

class SpendingSummary(BaseModel):
    """Comprehensive spending summary for period."""
    period: TimePeriod
    spending_analysis: PeriodSpendingAnalysis
    tax_optimization: TaxOptimizationAnalysis
    trends: list[SpendingTrend]
    recommendations: list[BusinessRecommendation]

class TaxSuggestion(BaseModel):
    """Tax optimization suggestion."""
    type: str
    title: str
    description: str
    potential_impact: Decimal
    action_items: list[str]
    compliance_references: list[str] = Field(default_factory=list)
```

## Testing Requirements

### Unit Tests
- [ ] Test business intelligence insights generation
- [ ] Test spending analysis calculations
- [ ] Test tax optimization suggestions
- [ ] Test CLI output formatting
- [ ] Test summary report generation

### Integration Tests
- [ ] Test end-to-end insights with real receipt data
- [ ] Test spending summaries with historical data
- [ ] Test export functionality
- [ ] Test CLI commands and output
- [ ] Test performance with large datasets

## Dependencies
- Existing expense processing ✅ Completed
- Provincial tax management (PRE-116) - Concurrent development
- Audit logging system (PRE-117) - Concurrent development

## Definition of Done
- [ ] Enhanced receipt output with business insights
- [ ] Spending summary commands with time period options
- [ ] Tax optimization suggestions and compliance warnings
- [ ] Export capabilities for reports (PDF, CSV)
- [ ] Interactive recommendations based on spending patterns
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate insights accuracy
- [ ] CLI user experience is intuitive and helpful
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)

## Validation Scenarios

### Scenario 1: Receipt Processing with Insights
**Given** processing a $150 restaurant receipt in September
**When** using enhanced CLI output
**Then**
- Standard categorization and QB integration shown
- Meals limitation warning displayed (50% deductible)
- YTD meals tracking shows progress toward annual total
- Recommendation to document business purpose
- Context shows this is 15% higher than average meal expense

### Scenario 2: Monthly Spending Summary
**Given** requesting September 2025 spending summary
**When** running `quickexpense summary --month 2025-09`
**Then**
- Total expenses and deductibility breakdown shown
- Category spending with percentages displayed
- Provincial tax impact analysis included
- Equipment vs expense recommendations provided
- Trend analysis compared to previous months
- Export option generates PDF for accountant

### Scenario 3: Tax Optimization Analysis
**Given** year-end tax planning in December
**When** analyzing annual spending patterns
**Then**
- Meals limitation impact calculated accurately
- Equipment purchase timing suggestions provided
- Provincial tax optimization opportunities identified
- Missing expense categories highlighted
- CRA compliance checklist generated
- Potential tax savings quantified

## Risk Mitigation
- **Data Privacy:** Ensure insights don't expose sensitive information
- **Performance:** Optimize analysis for large datasets
- **Accuracy:** Validate calculations against CRA requirements
- **User Experience:** Balance detail with readability

## Success Metrics
- Users identify 2+ tax optimization opportunities per month
- 25% improvement in expense categorization accuracy
- 90% user satisfaction with insights quality
- 50% reduction in manual expense analysis time
- 100% accuracy in tax calculation insights
