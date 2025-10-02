# Multi-Agent Receipt Processing System - Implementation Tickets

## Executive Summary

**Problem**: Users don't trust our receipt processing system because it's a black box. They can't see how tax decisions are made, which CRA rules apply, or why certain amounts are deductible. The current single-pass processor has no validation mechanism and the UI isn't accountant-friendly.

**Solution**: Build a transparent multi-agent system where specialized agents collaborate to process receipts, with clear confidence scoring and CRA rule visibility. Start simple with CSV-based rules and basic consensus, allowing rapid iteration based on user feedback.

**Approach**: 80/20 principle - deliver maximum value with minimum complexity. Use ag2 (autogen) for agents, CSV for rules (not a database), and focus on transparency over sophistication.

---

## EPIC: Multi-Agent Receipt Processing with CRA Compliance

### Success Metrics
- Users see exact CRA rules and ITA sections applied to their expenses
- Confidence scores help users identify items needing review
- Export to CSV works seamlessly with Excel/Google Sheets
- Processing time stays under 3 seconds
- 90% of common receipts process without manual intervention

---

## Ticket 1: Multi-Agent Architecture with ag2

**Priority**: P0 - Critical Path
**Effort**: 2 days
**Team**: Backend
**Dependencies**: None

### Why This Matters
Currently, our Gemini-based processor is a single point of failure. If it miscategorizes an expense or calculates tax wrong, users have no visibility into what went wrong. By splitting responsibilities across specialized agents, we create checkpoints and validation at each step.

### What We're Building
A 3-agent system using ag2 (autogen) library where each agent has a specific expertise:
1. **Data Extraction Agent** - Focuses solely on reading receipt data accurately
2. **CRA Rules Agent** - Applies Canadian tax law and categorization
3. **Tax Calculator Agent** - Validates GST/HST/PST calculations

These agents will communicate through ag2's GroupChat mechanism, allowing them to share findings and reach consensus.

### Technical Approach
- Use ag2's `AssistantAgent` class for each specialized agent
- Implement `GroupChat` for agent coordination (max 6 rounds)
- Each agent returns structured data with confidence scores
- Final consensus based on weighted confidence averaging

### Acceptance Criteria
- [ ] System processes a receipt through all 3 agents sequentially
- [ ] Each agent provides a confidence score (0-1) for its output
- [ ] Consensus mechanism produces final result with overall confidence
- [ ] If overall confidence < 0.75, receipt is flagged for review
- [ ] Processing completes in under 3 seconds for typical receipts
- [ ] Agents can handle failures gracefully (if one fails, others continue)
- [ ] System logs each agent's decision for debugging

### Implementation Notes
- Start with sequential processing (agent 1 → 2 → 3) for simplicity
- Consensus = simple average of confidence scores initially
- Each agent should have access to shared context but make independent decisions
- Use Gemini API for all agents but with different prompts/roles

### Testing Approach
- Unit test each agent independently with mock data
- Integration test the full pipeline with real receipts
- Test failure scenarios (what if CRA agent times out?)
- Verify confidence scoring correlates with accuracy

---

## Ticket 2: CRA Rules Database (CSV-Based)

**Priority**: P0 - Enables agent system
**Effort**: 1 day
**Team**: Backend
**Dependencies**: None

### Why This Matters
We're currently hardcoding tax rules in our code, making it impossible for non-developers to update them. Canadian tax law is complex and changes frequently. We need a system that accountants can review and update without touching code.

### What We're Building
A CSV-based "database" of Canadian tax rules that can be edited in Excel. This is intentionally NOT a real database - we want maximum simplicity and editability.

### CSV Structure Required
```
category, t2125_line, deductibility_rate, ita_section, description, keywords, examples, audit_risk, confidence_threshold
```

### Core Categories to Include (Minimum)
1. **Meals & Entertainment** - 50% deductible (ITA Section 67.1)
2. **Office Supplies** - 100% deductible
3. **Travel-Accommodation** - 100% deductible
4. **Vehicle-Fuel** - 100% deductible (if business use)
5. **Professional Fees** - 100% deductible
6. **Telecommunications** - 100% deductible
7. **Home Office** - Prorated (special calculation needed)
8. **Advertising** - 100% deductible
9. **Insurance** - 100% deductible
10. **Bank Charges** - 100% deductible

### Acceptance Criteria
- [ ] CSV file with at least 10 categories covering 80% of common expenses
- [ ] Each rule includes T2125 line number for tax filing
- [ ] Each rule cites specific Income Tax Act section
- [ ] Keywords field enables text matching (comma-separated)
- [ ] Examples field shows common vendors (e.g., "Tim Hortons, Starbucks")
- [ ] Audit risk field (LOW/MEDIUM/HIGH) guides user attention
- [ ] CSV can be opened and edited in Excel without corruption
- [ ] Python class to load and query rules efficiently

### Implementation Notes
- Use pandas for CSV operations (already in our stack)
- Create a simple keyword matching algorithm (not ML initially)
- Return both the matched rule and confidence score
- Handle special cases like "PRORATED" for home office

### Future Migration Path
- Phase 1: CSV file (current)
- Phase 2: SQLite for better querying
- Phase 3: Vector database for semantic search
- Phase 4: Live connection to CRA documentation

---

## Ticket 3: Accounting Dashboard UI

**Priority**: P1 - User Experience
**Effort**: 2 days
**Team**: Frontend
**Dependencies**: Tickets 1 & 2 functional

### Why This Matters
Users currently see a developer-focused UI with JSON-like data. They need an Excel-like view that looks familiar to anyone who's used QuickBooks or done bookkeeping. The current UI doesn't show confidence scores, CRA rules, or allow bulk operations.

### What We're Building
An accounting ledger interface that:
- Looks like a traditional bookkeeping spreadsheet
- Shows all tax calculations transparently
- Highlights items needing review
- Exports cleanly to CSV for accountants

### Required UI Components

#### Summary Cards (Top of Page)
1. Total Expenses (sum of all receipts)
2. Total Deductible (sum of deductible amounts)
3. Items Needing Review (confidence < 75%)
4. High Audit Risk Items (requiring extra documentation)

#### Main Ledger Table Columns
- Date
- Vendor
- Category
- T2125 Line Number
- Amount
- GST/HST
- Deductible Amount
- Deductibility %
- Confidence Score (with color coding)
- Status Icon (✓ processed, ⚠ needs review)
- CRA Reference (hoverable for details)

#### Key Features
- Checkbox selection for bulk operations
- Row highlighting (yellow = needs review, red = high audit risk)
- Click any row for detailed breakdown
- Export button that generates clean CSV

### Acceptance Criteria
- [ ] Table displays all processed expenses in ledger format
- [ ] Summary cards show real-time totals
- [ ] Export produces CSV that opens correctly in Excel
- [ ] Confidence scores are color-coded (green >75%, yellow 50-75%, red <50%)
- [ ] Items with confidence <75% are highlighted for review
- [ ] CRA rule references are visible and clickable
- [ ] Table handles 100+ expenses without performance issues
- [ ] Mobile responsive (horizontal scroll for table)

### Implementation Notes
- Use existing table component library (don't build from scratch)
- CSV export should escape commas in text fields properly
- Include date range filter for year-end tax prep
- Consider pagination if >100 expenses

---

## Ticket 4: Agent-UI Integration Layer

**Priority**: P1
**Effort**: 1 day
**Team**: Full-stack
**Dependencies**: Tickets 1, 2, 3 complete

### Why This Matters
The agents produce rich data about their decision-making process, but we need to transform this into user-friendly information. This ticket bridges the gap between agent output and UI display.

### What We're Building
API endpoint and data transformation layer that:
- Receives uploaded receipts
- Orchestrates the 3-agent processing
- Transforms agent output into UI-friendly format
- Stores results for session persistence

### API Endpoint Specification
```
POST /api/process-receipt-with-agents
Input: multipart/form-data with image file
Output: ProcessedExpense object with confidence scores and CRA rules
```

### Data Transformation Requirements
Transform agent consensus output into:
- Flat structure for table display
- Separated confidence scores by category
- Human-readable CRA references
- Status determination based on thresholds

### Acceptance Criteria
- [ ] Single API endpoint processes receipts through all agents
- [ ] Response includes confidence breakdown by agent
- [ ] CRA rules are attached with human-readable descriptions
- [ ] Processing errors don't crash the system
- [ ] Response format matches UI component expectations
- [ ] Session storage maintains receipts for current session
- [ ] API returns within 3 seconds for typical receipts

### Implementation Notes
- Add request ID for tracking through logs
- Cache Gemini responses to avoid duplicate API calls
- Return partial results if one agent fails
- Include processing time in response for monitoring

---

## Ticket 5: Testing & User Feedback Loop

**Priority**: P1
**Effort**: 2 days
**Team**: Full-stack
**Dependencies**: All previous tickets

### Why This Matters
We're making assumptions about what users want. We need to validate that our transparency features actually build trust and that the UI meets their workflow needs.

### What We're Testing

#### Functional Tests
1. **Restaurant Receipt**: Should apply 50% deductibility for meals
2. **Office Supplies**: Should be 100% deductible
3. **Mixed Receipt**: Costco with both supplies and meals
4. **Foreign Currency**: USD receipt with CAD tax calculations
5. **Poor Quality Image**: Low confidence should trigger review

#### User Acceptance Tests
1. Can users understand why an expense was categorized?
2. Do confidence scores match user expectations?
3. Does the CSV export work with their accounting software?
4. Are CRA references helpful or confusing?
5. Is the processing time acceptable?

### Acceptance Criteria
- [ ] 10 real receipts process correctly with appropriate tax treatment
- [ ] Confidence scores correlate with accuracy (>80% correlation)
- [ ] 5 beta users successfully export and use CSV data
- [ ] User feedback collected on trust and transparency
- [ ] Performance baseline established (<3 seconds p95)
- [ ] Error scenarios handled gracefully

### Feedback Collection Plan
- In-app feedback widget on dashboard
- Weekly check-in with beta users
- Track which receipts get manually corrected
- Monitor confidence score overrides

---

## Implementation Schedule

### Week 1 - Foundation
**Days 1-2**: Backend team implements Tickets 1 & 2 (Agents + CRA Rules)
**Days 3-4**: Frontend team implements Ticket 3 (Dashboard UI)
**Day 5**: Full team on Ticket 4 (Integration)

### Week 2 - Polish & Launch
**Days 1-2**: Testing & bug fixes (Ticket 5)
**Days 3-4**: Beta user feedback and iterations
**Day 5**: Production deployment

---

## Risk Mitigation

### Technical Risks
- **Agent Timeout**: Set 2-second timeout per agent, return partial results
- **CSV Corruption**: Keep versioned backups, validate on load
- **Gemini API Limits**: Implement caching and rate limiting
- **UI Performance**: Paginate at 50 expenses, virtual scrolling for more

### User Risks
- **Over-trusting System**: Always show confidence scores prominently
- **Misunderstanding Tax Law**: Include disclaimers and links to CRA
- **Export Issues**: Test with Excel, Google Sheets, and QuickBooks

---

## Success Definition

### Week 1 Success
- Process 10 different receipt types correctly
- Show CRA rules for each expense
- Export working CSV file
- Beta users understand the confidence scores

### Month 1 Success
- 90% of receipts process without manual intervention
- Users report increased trust in categorization
- Accountants accept the exported CSV format
- Processing time consistently under 3 seconds

### Future Vision
- 50+ CRA rules covering edge cases
- Learning from user corrections
- Direct QuickBooks integration
- Multi-business support

---

## Notes for Engineering Team

### Why These Specific Technical Choices

**ag2 (autogen) over custom orchestration**: Battle-tested library that handles agent communication, retries, and state management. Don't reinvent the wheel.

**CSV over database**: Our accountant users can review and edit rules in Excel. Database would require building an admin UI we don't need yet.

**3 agents instead of 10**: Each additional agent adds 200-500ms latency. Three gives us validation without sacrificing speed.

**Simple confidence averaging**: Weighted scoring and ML-based confidence can come later. Start with something explainable.

**Session storage over persistent DB**: We're not ready for user accounts and data persistence. Session storage is good enough for MVP.

### What We're Explicitly NOT Building
- User authentication system
- Persistent storage of receipts
- Machine learning for categorization
- Complex agent debate mechanisms
- Real-time collaborative editing
- Mobile app
- Direct accounting software integration
- Multi-currency support beyond CAD/USD

### Definition of Done
- Code reviewed by senior engineer
- Unit tests pass with >80% coverage
- Integration tests cover happy path
- Documentation updated
- Deployed to staging environment
- Product owner accepts feature
