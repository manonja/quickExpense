# Web UI Results Display Improvement

## Ticket: Improve Receipt Processing Results Display

### Overview
The current web UI shows the upload card alongside the results after successful receipt processing, creating a confusing user experience. Additionally, business rules information is hidden in an expandable section when it should be prominently displayed as essential information.

### Problem Statement
1. **Upload card remains visible**: After processing a receipt, the upload zone is still displayed, suggesting users can upload another receipt while results are showing
2. **Business rules are hidden**: Important business rules information is tucked away in the "Show Details" expandable section
3. **Status card is not informative**: The third column shows basic status info instead of actionable business rules data

### Solution
Transform the results display to:
- Hide the upload section when results are shown
- Replace the "Status" card with "Business Rules Applied"
- Show business rules by default in the main three-column grid
- Keep only processing summary in the expandable details section

### Acceptance Criteria

#### 1. Upload Section Visibility
- [ ] Upload section (`class="upload-section"`) is hidden when results are displayed
- [ ] Upload section only reappears when user clicks "Process Another Receipt"
- [ ] No visual artifacts or layout shifts when hiding/showing the upload section

#### 2. Business Rules Card
- [ ] Third column title changes from "Status" to "Business Rules Applied"
- [ ] Business rules information displays in the main grid (not in expandable section)
- [ ] Shows rule name, category, account, and deductible percentage
- [ ] If no rules applied, shows "No business rules applied" message

#### 3. Results Grid Layout
- [ ] Three-column layout maintained: "Receipt", "Tax Deductibility", "Business Rules Applied"
- [ ] Grid remains responsive on mobile devices
- [ ] All essential information is visible without expanding details

#### 4. Expandable Details Section
- [ ] "Show Details" button remains functional
- [ ] Expandable section only contains "Processing Summary" information
- [ ] Business rules no longer appear in expandable section
- [ ] Smooth animation when expanding/collapsing

#### 5. Data Display Format
- [ ] Business rules show in a clean, scannable format
- [ ] Each rule displays:
  - Rule name/description
  - Category applied
  - QuickBooks account
  - Deductibility percentage
  - Amount affected
- [ ] Multiple rules stack vertically within the card

#### 6. Error Handling
- [ ] Upload section correctly reappears on error
- [ ] All state transitions handle edge cases properly
- [ ] No JavaScript console errors

### Technical Implementation

#### Files to Modify
1. `src/quickexpense/web/templates/index.html`
   - Update grid column titles
   - Restructure results display HTML

2. `src/quickexpense/web/static/js/app.js`
   - Update `showResults()` to hide upload section
   - Update `resetToUpload()` to show upload section
   - Rename `populateStatusBasic()` to `populateBusinessRulesBasic()`
   - Move business rules display logic to main grid
   - Update expandable details to only show processing summary

3. `src/quickexpense/web/static/css/app.css`
   - Add styles for business rules in grid format
   - Ensure proper spacing and typography

### Test Scenarios
1. **Successful Processing**
   - Upload receipt → Results display → Upload section hidden
   - Business rules visible in main grid
   - Click "Process Another Receipt" → Upload section reappears

2. **Dry Run Mode**
   - Same behavior as successful processing
   - "Dry Run" indicator still visible

3. **Error Cases**
   - Processing error → Error message shown → Upload section remains visible
   - Network error → Appropriate error handling → Can retry

4. **Multiple Rules**
   - Receipt with multiple business rules → All rules displayed clearly
   - Proper scrolling if many rules

5. **No Rules Applied**
   - Receipt with no matching rules → "No business rules applied" message

### Success Metrics
- Improved user clarity on what information is essential
- Reduced clicks needed to see important tax/business information
- Clear visual separation between upload and results states
- Faster comprehension of receipt processing outcomes

### Implementation Priority
High - This directly impacts user experience and the clarity of critical business information display.
