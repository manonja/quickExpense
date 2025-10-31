# RAG Integration Plan: Phased Rollout with Validation Gates

## 🎯 Overview
Integrate qe-tax-rag v0.2.4 into quickExpense CRArulesAgent using a phased approach with validation gates after each step. Each ticket is MECE (Mutually Exclusive, Collectively Exhaustive) with clear pass/fail criteria.

**Timeline**: 5-6 hours (fits in 1-2 work days)
**Demo Deadline**: 2 days
**Approach**: 80/20 focused on high-impact changes with incremental validation

---

## 📋 Ticket RAG-001: Environment Setup & Library Validation

### Objective
Install qe-tax-rag library and verify core functions (init, search) work in isolation.

### Time Estimate
30 minutes

### Dependencies
None

### Implementation Steps

1. **Add Dependency to pyproject.toml**
   ```toml
   dependencies = [
       # ... existing ...
       "qe-tax-rag==0.2.4",
   ]
   ```

2. **Install Package**
   ```bash
   uv sync
   ```

### Acceptance Criteria & Validation Commands

#### ✅ AC1: Package Installed Successfully
```bash
# Validation Command
uv sync

# Pass Criteria: Command completes without errors
# Fail Criteria: Dependency resolution errors, httpx conflicts
```

#### ✅ AC2: Database Initializes
```bash
# Validation Command
python -c "import qe_tax_rag as qe; qe.init(); print('✅ Database initialized successfully')"

# Pass Criteria:
# - Prints success message
# - File exists at ~/.qe_tax_rag/t4002.db
# - No exceptions raised

# Fail Criteria:
# - ImportError
# - FileNotFoundError
# - Permission denied errors
```

#### ✅ AC3: Version Check
```bash
# Validation Command
python -c "import qe_tax_rag as qe; qe.init(); print(qe.get_version())"

# Expected Output:
# {'library_version': '0.2.4', 'data_version': '2024.12', 'schema_version': '1.0'}

# Pass Criteria: Version matches 0.2.4
# Fail Criteria: Version mismatch or error
```

#### ✅ AC4: Search Functionality Works
```bash
# Validation Command
python -c "
import qe_tax_rag as qe
qe.init()
results = qe.search('meals restaurant client', expense_types=['meals'], top_k=3)
assert len(results) > 0, 'Search returned no results'
print(f'✅ Found {len(results)} results')
for r in results[:1]:
    print(f'   Citation: {r.citation_id}')
    print(f'   Content: {r.content[:100]}...')
    print(f'   Source: {r.source_url}')
"

# Pass Criteria:
# - Returns 1-5 results
# - Citation ID format: LINE-####
# - Content and source_url present
# - No exceptions

# Fail Criteria:
# - Empty results (AssertionError)
# - Missing fields
# - Exception raised
```

#### ✅ AC5: Test Multiple Expense Categories
```bash
# Validation Command
python -c "
import qe_tax_rag as qe
qe.init()

test_queries = [
    ('meals restaurant', ['meals']),
    ('vehicle mileage', ['vehicle']),
    ('office supplies', ['supplies']),
    ('home office', ['home_office']),
]

for query, types in test_queries:
    results = qe.search(query, expense_types=types, top_k=2)
    print(f'{query}: {len(results)} results')

print('✅ All categories tested')
"

# Pass Criteria: Each query returns >0 results
# Fail Criteria: Any query returns 0 results
```

### Debugging Guide

**Problem: ImportError**
- Check virtual environment: `which python`
- Verify package installed: `pip list | grep qe-tax-rag`
- Reinstall: `pip uninstall qe-tax-rag -y && uv sync`

**Problem: Database initialization fails**
- Check permissions: `ls -ld ~`
- Check disk space: `df -h ~`
- Try manual path: `python -c "import qe_tax_rag as qe; qe.init(path='/tmp/qe_rag_test')"`

**Problem: Empty search results**
- Use simpler query: `qe.search('meals', top_k=5)`
- Remove expense_types filter
- Check database file exists: `ls -lh ~/.qe_tax_rag/t4002.db`

### Rollback Plan
```bash
# Remove from pyproject.toml
# Then:
uv sync
rm -rf ~/.qe_tax_rag
```

---

## 📋 Ticket RAG-002: Service-Level Integration & Isolation

### Objective
Integrate RAG at application startup and create isolated helper function in CRArulesAgent without modifying existing workflow.

### Time Estimate
1.5 hours

### Dependencies
RAG-001 must pass all acceptance criteria

### Implementation Steps

1. **Add RAG initialization to FastAPI lifespan** (main.py)
2. **Create _get_rag_context() helper method** (cra_rules_agent.py)
3. **Do NOT modify existing agent methods yet**

### File Changes

#### File 1: `src/quickexpense/main.py`
```python
@asynccontextmanager
async def lifespan(app: FastAPIType) -> AsyncGenerator[None, None]:
    settings = get_settings()

    # ... existing initialization ...

    # Initialize RAG database
    try:
        import qe_tax_rag as qe
        qe.init()
        version = qe.get_version()
        logger.info(f"✅ RAG initialized: {version['library_version']}")
    except Exception as e:
        logger.warning(f"⚠️ RAG init failed (will use LLM only): {e}")

    yield
    # ... existing cleanup ...
```

#### File 2: `src/quickexpense/services/agents/cra_rules_agent.py`
```python
def _get_rag_context(
    self,
    expense_description: str,
    expense_category: str | None = None,
    vendor_name: str | None = None,
) -> str:
    """
    Retrieve and format CRA context from RAG database.

    Args:
        expense_description: Line items or description
        expense_category: Category hint (e.g., "meals", "travel")
        vendor_name: Vendor name for context

    Returns:
        Formatted context string for LLM prompt
    """
    try:
        import qe_tax_rag as qe

        # Build search query
        query_parts = [expense_description]
        if vendor_name:
            query_parts.append(vendor_name)
        query_parts.append("tax deduction rules")
        query = " ".join(filter(None, query_parts))

        # Search RAG database
        results = qe.search(
            query=query,
            expense_types=[expense_category] if expense_category else [],
            top_k=3
        )

        if not results:
            return "No specific CRA documents found. Rely on general tax knowledge."

        # Format results
        context_parts = ["Relevant CRA Documents Found:"]
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"\n{i}. Citation ID: {result.citation_id}"
                f"\n   Source: {result.source_url}"
                f"\n   Content: \"{result.content[:400]}...\""
            )

        return "\n".join(context_parts)

    except Exception as e:
        logger.warning(f"RAG search failed: {e}")
        return "RAG search failed. Rely on general tax knowledge."
```

### Acceptance Criteria & Validation Commands

#### ✅ AC1: FastAPI Starts with RAG
```bash
# Validation Command
uv run fastapi dev src/quickexpense/main.py

# Watch startup logs for:
# "✅ RAG initialized: 0.2.4"

# Pass Criteria:
# - Server starts without errors
# - RAG initialization log appears
# - Health check responds: curl http://localhost:8000/health

# Fail Criteria:
# - Server crashes on startup
# - No RAG log message
# - Exception in logs
```

#### ✅ AC2: Helper Function Works in Isolation
```bash
# Create test script: scripts/test_rag_helper.py
cat > scripts/test_rag_helper.py << 'EOF'
#!/usr/bin/env python
"""Test RAG helper function in isolation."""
import sys
sys.path.insert(0, 'src')

from quickexpense.services.agents.cra_rules_agent import CRArulesAgent
from quickexpense.core.config import get_settings

# Initialize agent
settings = get_settings()
agent = CRArulesAgent(settings=settings)

# Test cases
test_cases = [
    ("Client lunch meeting", "meals", "Tim Hortons"),
    ("Office printer paper", "supplies", "Staples"),
    ("Hotel accommodation", "travel", "Marriott"),
]

print("Testing RAG context retrieval...\n")
for desc, cat, vendor in test_cases:
    print(f"Test: {desc} ({vendor})")
    context = agent._get_rag_context(desc, cat, vendor)
    print(f"Context length: {len(context)} chars")
    assert "Citation ID" in context or "No specific CRA" in context
    print(f"✅ Pass\n")

print("All tests passed!")
EOF

# Run test
uv run python scripts/test_rag_helper.py

# Pass Criteria:
# - All 3 test cases print "✅ Pass"
# - Context contains "Citation ID: LINE-####" or fallback message
# - No exceptions

# Fail Criteria:
# - AssertionError
# - Exception raised
# - Empty context returned
```

#### ✅ AC3: Verify Context Quality
```bash
# Validation Command
python -c "
import sys
sys.path.insert(0, 'src')
from quickexpense.services.agents.cra_rules_agent import CRArulesAgent
from quickexpense.core.config import get_settings

agent = CRArulesAgent(settings=get_settings())
context = agent._get_rag_context('restaurant meal with client', 'meals', 'Restaurant ABC')

print(context)
print('\n--- Validation ---')
assert 'LINE-' in context, 'No citation found'
assert 'Source:' in context, 'No source URL'
assert '50' in context or 'deduct' in context.lower(), 'No deduction info'
print('✅ Context quality validated')
"

# Pass Criteria:
# - Citation ID present (LINE-####)
# - Source URL present (https://...)
# - Relevant content about deductibility
# - Formatted for readability

# Fail Criteria:
# - AssertionError
# - Malformed output
# - Irrelevant content
```

### Debugging Guide

**Problem: Server fails to start**
- Check import path: `python -c "import qe_tax_rag"`
- Check lifespan syntax: Look for indentation errors
- Add debug logging: `print(f"About to init RAG...")` before `qe.init()`

**Problem: Helper function returns fallback**
- Test query directly: `qe.search('meals', top_k=5)`
- Check logger output: Look for "RAG search failed" warnings
- Verify database: `ls -lh ~/.qe_tax_rag/t4002.db`

**Problem: Context is empty or malformed**
- Add debug prints in `_get_rag_context()`:
  ```python
  print(f"Query: {query}")
  print(f"Results: {len(results)}")
  for r in results:
      print(f"  {r.citation_id}: {r.content[:50]}")
  ```

### Rollback Plan
```bash
# Revert main.py changes
git checkout src/quickexpense/main.py

# Comment out or delete _get_rag_context method
# Agent still works with original logic
```

---

## 📋 Ticket RAG-003: Agent Prompt Augmentation & E2E Validation

### Objective
Integrate RAG context into CRArulesAgent prompts and validate end-to-end with real receipts via CLI.

### Time Estimate
2-3 hours

### Dependencies
RAG-002 must pass all acceptance criteria

### Implementation Steps

1. **Modify _build_refinement_prompt()** to inject RAG context
2. **Modify _build_fallback_prompt()** to inject RAG context
3. **Update response parsing** to extract citations
4. **Add verbose logging** for debugging
5. **Test with real receipts** via CLI

### File Changes

#### File: `src/quickexpense/services/agents/cra_rules_agent.py`

**Modify _build_refinement_prompt():**
```python
def _build_refinement_prompt(
    self,
    receipt_data: dict[str, Any],
    best_match: Any,
    all_matches: list[Any],
) -> str:
    """Build prompt with RAG context for refining categorization."""

    # GET RAG CONTEXT (NEW)
    vendor_name = receipt_data.get("vendor_name", "")
    line_items_text = self._format_line_items(receipt_data.get("line_items", []))

    rag_context = self._get_rag_context(
        expense_description=line_items_text,
        expense_category=best_match.rule.category,
        vendor_name=vendor_name,
    )

    # BUILD PROMPT WITH CONTEXT (MODIFIED)
    return f"""
Analyze this business expense and validate the suggested CRA categorization:

**AUTHORITATIVE CRA CONTEXT:**
---
{rag_context}
---

**EXPENSE DETAILS:**
- Vendor: {vendor_name}
- Line Items: {line_items_text}
- Total Amount: ${receipt_data.get("total_amount", 0)}

**SUGGESTED CATEGORIZATION:**
- Category: {best_match.rule.category}
- Deductibility: {best_match.rule.deductibility_rate}%
- T2125 Line: {best_match.rule.t2125_line}
- ITA Section: {best_match.rule.ita_section}

**YOUR TASK:**
1. Review the AUTHORITATIVE CRA CONTEXT above
2. If relevant, you MUST base your reasoning on it
3. Include citation IDs from the context in your response
4. Validate or refine the suggested categorization

Return JSON:
{{
    "category": "string",
    "deductibility_percentage": number,
    "qb_account": "string",
    "tax_treatment": "string",
    "ita_section": "string",
    "audit_risk": "LOW|MEDIUM|HIGH",
    "t2125_line": "string",
    "rule_applied": "string",
    "citations": ["LINE-####", ...],
    "reasoning": "string (MUST reference citations if used)",
    "confidence_adjustment": number
}}
"""
```

**Similar modifications for _build_fallback_prompt()**

**Add verbose logging:**
```python
async def _process_internal(
    self,
    receipt_data: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Apply CRA rules with RAG enhancement."""

    # ... existing logic ...

    prompt = self._build_refinement_prompt(receipt_data, best_match, rule_matches)

    # VERBOSE LOGGING (NEW - for debugging only)
    logger.debug("=" * 80)
    logger.debug("LLM PROMPT WITH RAG CONTEXT:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    # ... rest of processing ...
```

### Acceptance Criteria & Manual Testing Workflow

#### ✅ AC1: Establish Baseline (Before Integration)
```bash
# Save current state
git stash

# Process test receipt WITHOUT RAG
uv run quickexpense upload tests/fixtures/restaurant_receipt.jpg --output json > baseline.json

# Verify baseline
cat baseline.json | jq '.category, .deductibility_percentage, .reasoning'

# Expected: Valid response, no citations field
# Pass Criteria: Command succeeds, valid JSON
# Fail Criteria: Command fails, invalid JSON
```

#### ✅ AC2: Deploy RAG Integration
```bash
# Apply all changes from RAG-003
git stash pop

# Restart server (if running)
pkill -f "fastapi dev"
uv run fastapi dev src/quickexpense/main.py &

# Wait for startup
sleep 3
```

#### ✅ AC3: Process Same Receipt WITH RAG
```bash
# Enable verbose logging (add to .env)
echo "LOG_LEVEL=DEBUG" >> .env

# Process same receipt
uv run quickexpense upload tests/fixtures/restaurant_receipt.jpg --output json > rag_enhanced.json

# Check logs for RAG context
# Should see: "AUTHORITATIVE CRA CONTEXT:" in debug output

# Pass Criteria:
# - Command succeeds
# - Debug logs show RAG context in prompt
# - Valid JSON output

# Fail Criteria:
# - Command fails
# - No RAG context in logs
# - Invalid JSON
```

#### ✅ AC4: Validate Citations Added
```bash
# Validation Command
cat rag_enhanced.json | jq '.citations'

# Expected output: ["LINE-8523"] or similar

# Pass Criteria:
# - citations field exists
# - Contains at least one LINE-#### citation
# - Citations match those from RAG context in logs

# Fail Criteria:
# - No citations field
# - Empty citations array
# - Citations don't match RAG results
```

#### ✅ AC5: Validate Reasoning Improved
```bash
# Compare reasoning
echo "=== BASELINE REASONING ==="
cat baseline.json | jq -r '.reasoning'

echo ""
echo "=== RAG-ENHANCED REASONING ==="
cat rag_enhanced.json | jq -r '.reasoning'

# Pass Criteria:
# - RAG reasoning is more specific
# - RAG reasoning references citations (e.g., "Based on LINE-8523...")
# - RAG reasoning mentions specific rules (e.g., "50% deductible")

# Fail Criteria:
# - Reasoning identical to baseline
# - No citation references in reasoning
# - Reasoning is less clear or shorter
```

#### ✅ AC6: Side-by-Side Comparison
```bash
# Validation Command
diff <(jq -S . baseline.json) <(jq -S . rag_enhanced.json)

# Pass Criteria:
# - Diff shows addition of "citations" field
# - Diff shows improved "reasoning" text
# - All other fields remain valid
# - deductibility_percentage is reasonable (0-100)

# Fail Criteria:
# - No meaningful differences
# - Deductibility changed incorrectly
# - Invalid JSON structure
```

#### ✅ AC7: Test Multiple Receipt Types
```bash
# Create test script
cat > scripts/test_multiple_receipts.sh << 'EOF'
#!/bin/bash
set -e

RECEIPTS=(
    "tests/fixtures/restaurant_receipt.jpg:meals:LINE-8523"
    "tests/fixtures/office_supplies.jpg:supplies:LINE-"
    "tests/fixtures/hotel_receipt.jpg:travel:LINE-"
)

echo "Testing multiple receipt types..."
for receipt_spec in "${RECEIPTS[@]}"; do
    IFS=':' read -r file category expected_pattern <<< "$receipt_spec"

    echo ""
    echo "Testing: $file"
    result=$(uv run quickexpense upload "$file" --output json)

    # Validate category
    actual_cat=$(echo "$result" | jq -r '.category')
    echo "  Category: $actual_cat"

    # Validate citations
    citations=$(echo "$result" | jq -r '.citations[]' 2>/dev/null || echo "none")
    echo "  Citations: $citations"

    if [[ "$citations" == *"$expected_pattern"* ]]; then
        echo "  ✅ PASS"
    else
        echo "  ⚠️ WARNING: Expected citation pattern not found"
    fi
done

echo ""
echo "All receipts processed!"
EOF

chmod +x scripts/test_multiple_receipts.sh
./scripts/test_multiple_receipts.sh

# Pass Criteria:
# - All receipts process successfully
# - At least 3/5 have citations
# - No crashes or invalid JSON

# Fail Criteria:
# - Any receipt fails to process
# - All citations empty
# - JSON parsing errors
```

### Debugging Guide

**Problem: Citations not appearing**
- Check debug logs: Look for RAG context in prompt
- Verify LLM sees instructions: Search logs for "citations"
- Test prompt manually: Copy prompt to LLM playground
- Make instructions more forceful: Add to top of prompt in ALL CAPS

**Problem: Reasoning doesn't reference citations**
- Add explicit instruction: "Your reasoning MUST start with: 'Based on [Citation ID]...'"
- Reduce top_k: Try `top_k=1` to give LLM less to process
- Check citation relevance: Verify RAG results match expense type

**Problem: JSON parsing fails**
- Check for JSON in RAG content: Content might contain `{` or `}` characters
- Escape special characters in `_get_rag_context()`:
  ```python
  content = result.content.replace('"', '\\"')
  ```
- Add JSON validation before returning

**Problem: Performance degradation**
- Check RAG query latency: Add timing logs
- Cache search results: Use `@lru_cache` on `_get_rag_context`
- Reduce top_k: Try `top_k=2` instead of 3

### Rollback Plan
```bash
# Revert all changes
git checkout src/quickexpense/services/agents/cra_rules_agent.py

# System returns to RAG-002 state:
# - RAG service initialized
# - Helper function exists but unused
# - Original agent logic intact
```

---

## 📊 Final Validation Checklist

Before considering integration complete, validate:

- [ ] All RAG-001 acceptance criteria pass
- [ ] All RAG-002 acceptance criteria pass
- [ ] All RAG-003 acceptance criteria pass
- [ ] At least 3 different receipt types tested successfully
- [ ] Citations appear in 80%+ of processed receipts
- [ ] No performance regression (processing time <2 seconds)
- [ ] All pre-commit hooks pass (`uv run pre-commit run --all-files`)
- [ ] Documentation updated (CLAUDE.md)
- [ ] Demo rehearsal completed (3 sample receipts)

---

## 🎬 Demo Preparation Script

```bash
# Demo script: scripts/demo_rag_integration.sh
cat > scripts/demo_rag_integration.sh << 'EOF'
#!/bin/bash
echo "🎬 QuickExpense RAG Integration Demo"
echo "===================================="
echo ""

# Sample receipts for demo
DEMO_RECEIPTS=(
    "tests/fixtures/restaurant_client_lunch.jpg"
    "tests/fixtures/hotel_with_fees.jpg"
    "tests/fixtures/office_supplies.jpg"
)

for receipt in "${DEMO_RECEIPTS[@]}"; do
    echo "📄 Processing: $(basename $receipt)"
    echo "---"

    result=$(uv run quickexpense upload "$receipt" --output json)

    # Extract key fields
    category=$(echo "$result" | jq -r '.category')
    deduct=$(echo "$result" | jq -r '.deductibility_percentage')
    citations=$(echo "$result" | jq -r '.citations | join(", ")')
    reasoning=$(echo "$result" | jq -r '.reasoning' | head -c 200)

    echo "✓ Category: $category"
    echo "✓ Deductible: ${deduct}%"
    echo "✓ Citations: $citations"
    echo "✓ Reasoning: $reasoning..."
    echo ""
done

echo "✅ Demo complete!"
EOF

chmod +x scripts/demo_rag_integration.sh
```

---

## 📝 Post-Integration Tasks

After successful demo:

1. **Migrate to production PyPI** (when available)
   ```bash
   pip uninstall qe-tax-rag
   pip install qe-tax-rag==0.2.4  # From production PyPI
   ```

2. **Remove debug logging** (verbose prompt dumps)

3. **Add query caching** for performance
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=100)
   def _cached_rag_search(query: str, category: str) -> list:
       return qe.search(query, expense_types=[category], top_k=3)
   ```

4. **Expand test coverage** (unit + integration tests)

5. **Monitor production metrics** (citation rate, query latency)

---

## 🎯 Success Metrics

Track these metrics to validate RAG value:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Citation Rate | >80% | % of expenses with citations |
| Query Latency | <250ms | Average RAG search time |
| Reasoning Quality | Improved | Manual review of 20 samples |
| Accuracy | Maintained or better | Compare to baseline test set |
| Error Rate | <0.1% | RAG failures / total queries |

---

## 🔗 References

- **qe-tax-rag Package**: [TestPyPI](https://test.pypi.org/project/qe-tax-rag/0.2.4/)
- **Integration Guide**: `docs/integration_guide.md` (from qe-tax-rag repo)
- **CRA T4002 Guide**: [canada.ca/t4002](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4002.html)
- **quickExpense Docs**: `CLAUDE.md`

---

## Summary

This plan provides:
- ✅ **MECE Tickets**: Three non-overlapping phases
- ✅ **Validation Gates**: Clear pass/fail after each phase
- ✅ **Manual Testing**: Explicit CLI commands for each check
- ✅ **Debugging Guide**: What can go wrong and how to fix
- ✅ **Rollback Strategy**: Safe reversion at any point
- ✅ **Real-world Testing**: Actual receipts, not mocks
- ✅ **Demo-ready**: Script for presentation

**Total Time: 5-6 hours** (fits in 1-2 work days with buffer)
