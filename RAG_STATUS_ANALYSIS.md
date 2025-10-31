# RAG Integration Status Analysis and Fix Plan

**Date**: 2025-10-30
**Analysis**: Comprehensive review of RAG integration with zen expert consultation

---

## 🔍 Current State Assessment

### ✅ **What's Implemented (RAG-001 & RAG-002 Complete)**

1. **Package Installation** ✅
   - `qe-tax-rag==0.2.4` installed from test-pypi
   - Location: `pyproject.toml` line 28
   - Package source configured (lines 49-54)

2. **RAG Initialization** ✅
   - Database initializes on app startup
   - Location: `main.py` lines 134-145
   - Logs: `"✅ RAG initialized: 0.2.4 (data: 2024.12)"`

3. **Helper Method** ✅
   - `_get_rag_context()` implemented
   - Location: `cra_rules_agent.py` lines 704-756
   - Performs search: `qe.search(query, expense_types, top_k=3)`
   - Returns formatted context with citation IDs

4. **Prompt Integration** ✅
   - `_build_refinement_prompt()` calls RAG helper (line 336)
   - `_build_fallback_prompt()` calls RAG helper (line 424)
   - Both include "**AUTHORITATIVE CRA CONTEXT:**" section

5. **Response Schema** ✅
   - Citations field defined in prompts (line 387, 475)
   - Parser initializes citations field (line 543)

---

## ⚠️ **Critical Problem: RAG-003 Incomplete**

### **The RAG system is likely failing silently.**

### Evidence of Failure:

1. **Missing Citations in Output**
   - Test results (AGENTS_VS_BASELINE_TEST_RESULTS.md) show only generic "ITA Section 67.1"
   - **ZERO `LINE-####` citations** in any agent responses
   - This is the smoking gun that RAG is not working

2. **LLM Using General Knowledge**
   - "ITA Section 67.1" is well-known Canadian tax law (50% meals rule)
   - Any LLM trained on web data knows this without RAG
   - No specific CRA document references = RAG not being used

3. **Citation Format Mismatch**
   - Code returns: `result.citation_id` (format: `"LINE-####"`)
   - Prompts show: `"T4002-####"` as example
   - LLM may be confused by inconsistent format

4. **No RAG Logs Visible**
   - Server startup shows RAG initialization
   - But no logs during request processing
   - Suggests silent failure or no results

---

## 🎯 Root Cause Diagnosis (From Zen Expert)

### Primary Hypothesis: **RAG Returns No Results**

```
RAG Search Flow:
1. _get_rag_context() called ✅
2. qe.search(query, expense_types, top_k=3) ❓ Returns []
3. if not results: return fallback message ⚠️
4. LLM receives empty/generic context
5. LLM uses internal knowledge only
6. Output: "ITA Section 67.1" (no LINE-#### citations)
```

### Why RAG Might Return Nothing:

1. **Query Construction Issue**
   - Current: `expense_description + vendor_name + "tax deduction rules"`
   - May not match indexed document content

2. **Expense Type Filtering**
   - Passing category like `"Travel-Lodging"` as expense_type
   - RAG expects: `["meals", "travel", "vehicle"]`
   - Mismatch causes empty results

3. **Database Content**
   - Documents may not be indexed properly
   - Search embeddings may not match query embeddings

4. **Silent Exception**
   - Exception caught and logged as warning
   - Returns fallback message silently

---

## 📋 Fix Plan (4 Steps)

### **Step 1: Add Debug Logging** ⚡ CRITICAL

**Goal**: See exactly what RAG returns and what gets injected into prompts

**Changes to `_get_rag_context()` in `cra_rules_agent.py`**:

```python
def _get_rag_context(
    self,
    expense_description: str,
    expense_category: str | None = None,
    vendor_name: str | None = None,
) -> str:
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
            top_k=3,
        )

        # 🆕 ADD: Enhanced logging to see raw results
        logger.debug("RAG search query: %s", query)
        logger.debug("RAG search expense_types: %s", [expense_category] if expense_category else [])
        logger.debug("RAG search raw results count: %d", len(results) if results else 0)
        if results:
            logger.debug("RAG search raw results: %s",
                        [{"id": r.citation_id, "content": r.content[:100]} for r in results])

        if not results:
            # 🆕 CHANGE: Explicit message instead of generic fallback
            logger.warning("RAG search returned no results for query: %s", query)
            return "No specific CRA documents found. Rely on general tax knowledge."

        # Format results
        context_parts = ["Relevant CRA Documents Found:"]
        for i, result in enumerate(results, 1):
            # Escape quotes to prevent JSON issues
            content = result.content[:400].replace('"', '\\"')
            entry = (
                f"\n{i}. Citation ID: {result.citation_id}\n"
                f"   Source: {result.source_url}\n"
                f'   Content: "{content}..."'
            )
            context_parts.append(entry)

        formatted_context = "\n".join(context_parts)

        # 🆕 ADD: Log the exact context being injected
        logger.debug("Formatted RAG context being injected into prompt:\n%s", formatted_context)

        return formatted_context

    except Exception as e:
        logger.warning("RAG search failed: %s", e)
        return "RAG search failed. Rely on general tax knowledge."
```

**Expected Log Output**:
```
DEBUG - RAG search query: Restaurant Room Charge Marriott tax deduction rules
DEBUG - RAG search expense_types: ['Travel-Meals']
DEBUG - RAG search raw results count: 3
DEBUG - RAG search raw results: [{'id': 'LINE-8523', 'content': 'Meals and entertainment expenses...'}, ...]
DEBUG - Formatted RAG context being injected into prompt:
Relevant CRA Documents Found:
1. Citation ID: LINE-8523
   Source: https://www.canada.ca/...
   Content: "Meals and entertainment expenses..."
```

---

### **Step 2: Fix Citation Format Mismatch** 🔧

**Goal**: Align prompt examples with actual data format

**Changes to `_build_refinement_prompt()` (line ~387)**:

```python
# BEFORE (line 387):
"citations": ["T4002-####", ...],

# AFTER:
"citations": ["LINE-####", ...],
```

**Changes to `_build_fallback_prompt()` (line ~475)**:

```python
# BEFORE (line 475):
"citations": ["T4002-####", ...],

# AFTER:
"citations": ["LINE-####", ...],
```

**Also update instruction text** to use consistent examples:
```python
# In both prompts, change:
4. If the CRA context above contains relevant citations, you MUST:
   - Reference them in your reasoning
   - Include the citation IDs in a "citations" field (e.g., ["LINE-8523"])
   - Base your decision on the official CRA guidance
```

---

### **Step 3: Test with Debug Logging** 🧪

**Setup**:
```bash
# 1. Enable debug logging
export LOG_LEVEL=DEBUG

# 2. Restart server
pkill -f "fastapi dev"
uv run fastapi dev src/quickexpense/main.py

# 3. Watch logs in terminal
```

**Test Cases**:
```bash
# Test 1: Restaurant meal (should match meals documents)
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@tests/fixtures/restaurant_receipt.jpg" \
  -F "additional_context=Client lunch meeting" \
  -F "dry_run=true" | jq '.agent_details.full_agent_data.line_items[0].citations'

# Expected: ["LINE-8523"] or similar
# If empty: Check logs for "RAG search returned no results"

# Test 2: Hotel receipt (should match travel documents)
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@marriot.pdf" \
  -F "additional_context=Hotel accommodation" \
  -F "dry_run=true" | jq '.agent_details.full_agent_data.line_items[].citations'

# Expected: Multiple line items with citations
```

**What to Look For in Logs**:
1. ✅ `DEBUG - RAG search raw results count: 3` (not 0)
2. ✅ `DEBUG - RAG search raw results: [{'id': 'LINE-...'}]`
3. ✅ `DEBUG - Formatted RAG context being injected into prompt:`
4. ❌ `WARNING - RAG search returned no results` (problem!)

---

### **Step 4: Diagnose and Fix Query Issues** 🔍

**If Step 3 shows "no results"**, diagnose query construction:

#### Option A: Test RAG Directly
```python
# Create test script: scripts/test_rag_direct.py
import qe_tax_rag as qe

qe.init()

# Test 1: Simple query
results = qe.search("meals restaurant", expense_types=["meals"], top_k=5)
print(f"Simple query: {len(results)} results")
for r in results[:2]:
    print(f"  {r.citation_id}: {r.content[:80]}")

# Test 2: Complex query (like agent uses)
results = qe.search(
    "Restaurant Room Charge Marriott tax deduction rules",
    expense_types=["Travel-Meals"],  # Note: May need lowercase "meals"
    top_k=3
)
print(f"\nComplex query: {len(results)} results")

# Test 3: Without expense_types filter
results = qe.search("meals restaurant 50%", expense_types=[], top_k=3)
print(f"\nNo filter: {len(results)} results")
```

```bash
uv run python scripts/test_rag_direct.py
```

#### Option B: Fix Expense Type Mapping

If RAG expects lowercase categories:
```python
# In _get_rag_context(), add mapping:
CATEGORY_TO_EXPENSE_TYPE = {
    "Travel-Meals": "meals",
    "Travel-Lodging": "lodging",
    "Travel-Taxes": "travel",
    "Fuel-Vehicle": "vehicle",
    "Office-Supplies": "supplies",
    # ... etc
}

expense_type_param = CATEGORY_TO_EXPENSE_TYPE.get(expense_category, "")
results = qe.search(
    query=query,
    expense_types=[expense_type_param] if expense_type_param else [],
    top_k=3,
)
```

#### Option C: Simplify Query Construction

If complex queries fail:
```python
# Simpler query construction
if expense_category:
    query = f"{expense_category} {expense_description}"
else:
    query = expense_description
# Don't add "tax deduction rules" suffix - too specific
```

---

## 🎬 Demo Readiness Assessment

### Current Status: ❌ **NOT DEMO-READY**

**Why**: RAG appears non-functional (no citations in output)

### After Fixes: ✅ **DEMO-READY IF:**

1. ✅ Server logs show RAG initialization on startup
2. ✅ At least **80% of receipts** get LINE-#### citations
3. ✅ Citations are in correct format: `["LINE-8523"]`
4. ✅ Reasoning text references citations: "Based on LINE-8523..."
5. ✅ Processing time remains <20 seconds per receipt
6. ✅ No exceptions or errors in logs

---

## 📊 Success Criteria Checklist

### Phase Completion Markers:

**RAG-001: Environment Setup** ✅
- [x] Package installed (`qe-tax-rag==0.2.4`)
- [x] Database initializes (`qe.init()` succeeds)
- [x] Version check passes
- [x] Search functionality works in isolation

**RAG-002: Service-Level Integration** ✅
- [x] RAG initialized in FastAPI lifespan
- [x] `_get_rag_context()` helper method exists
- [x] Helper can search and format results
- [x] No crashes on startup

**RAG-003: Agent Prompt Augmentation** ⚠️ IN PROGRESS
- [x] RAG context injected into prompts
- [x] Prompts instruct LLM to use citations
- [x] Response parser handles citations field
- [ ] **MISSING**: Citations appear in actual output ❌
- [ ] **MISSING**: Reasoning references citations ❌
- [ ] **MISSING**: Debug logs confirm RAG results ❌

---

## 🔑 Key Insights from Zen Expert

### On Citation Evidence:

> "A functioning RAG system retrieves specific chunks of text from a vectorized document. The citation `LINE-####` (or a similar unique identifier for the text chunk) is the **proof** that the agent isn't just reciting general knowledge but is actively retrieving and referencing a specific passage from the source material you provided to it."

### On ITA vs LINE Citations:

- **"ITA Section 67.1"**: Topical reference (like "Chapter 5"). LLM knows this from training data.
- **"LINE-8523"**: Retrieval citation (like "page 94, paragraph 3"). Proves RAG actually retrieved text.

### On Current Status:

> "Based on this analysis, you are most likely at the end of **RAG-001**. The critical RAG data retrieval step, as defined in your plan for RAG-002 (implementing `_get_rag_context` and using its output), does not appear to be active yet."

---

## 🚀 Next Steps Priority

1. **IMMEDIATE**: Add debug logging (Step 1) to see what RAG returns
2. **QUICK WIN**: Fix citation format mismatch (Step 2)
3. **VALIDATION**: Run test with debug logs (Step 3)
4. **DIAGNOSIS**: If no results, test RAG directly (Step 4)
5. **ITERATION**: Adjust query construction based on findings

---

## 📁 Related Files

- **Integration Plan**: `docs/RAG_INTEGRATION_PLAN.md`
- **Test Results**: `AGENTS_VS_BASELINE_TEST_RESULTS.md`
- **CRA Agent**: `src/quickexpense/services/agents/cra_rules_agent.py`
- **Main App**: `src/quickexpense/main.py`
- **Zen Suggestions**: `zen_generated.code` (reference only, not for wholesale copy)

---

## 🤝 Collaboration Notes

This analysis was created with consultation from zen (gemini-2.5-pro) expert model using the `mcp__zen__chat` tool. The diagnosis combines:
- Static code analysis (file inspection)
- Test output analysis (AGENTS_VS_BASELINE_TEST_RESULTS.md)
- RAG integration plan review (docs/RAG_INTEGRATION_PLAN.md)
- Expert reasoning on RAG failure modes

**Continuation ID**: `43ffe61a-5f07-4100-bee1-df42eb2cc26f` (44 turns remaining)

---

**End of Analysis** | Generated: 2025-10-30
