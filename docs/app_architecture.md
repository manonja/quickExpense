# QuickExpense: Technical Architecture Overview

## System Purpose
AI-powered multi-agent receipt processing system that automatically extracts expense data and syncs to QuickBooks with Canadian tax compliance.

---

## AI Model Architecture: Hybrid Gemini + TogetherAI

### Multi-Agent System Implementation

The system uses a hybrid approach combining Google Gemini (vision) and TogetherAI (reasoning) across a 3-agent architecture:

**Agent 1: Data Extraction Agent**
- Vision: Gemini 2.0 Flash (image processing)
- Reasoning: microsoft/phi-2 (TogetherAI)
- Extracts vendor, items, amounts, dates
- Confidence: 0.95 typical

**Agent 2: CRA Rules Agent**
- Model: meta-llama/Llama-3.3-70B-Instruct-Turbo
- Provider: TogetherAI
- Applies Canadian tax law categorization
- Uses CSV-based business rules (15 categories)

**Agent 3: Tax Calculator Agent**
- Model: meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
- Provider: TogetherAI
- Validates GST/HST calculations and deductibility
- Checks provincial tax rates and ITC eligibility
- Confidence: 0.8 typical

**Agent Orchestrator**
- Consensus-based decision making
- Combines agent outputs with weighted scores
- Structured logging with correlation IDs

---

## Model Specifications

### Agent 1: Data Extraction
**Vision Processing:**
- Model: `gemini-2.0-flash-exp`
- Provider: Google AI
- Token Limit: 2.3M tokens
- Supports HEIC, PDF, large files

**Text Validation:**
- Model: `microsoft/phi-2` (2.7B parameters)
- Provider: TogetherAI
- Cost: ~$0.0001 per request

### Agent 2: CRA Rules
- Model: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- Provider: TogetherAI
- Parameters: 70B
- Cost: ~$0.0006 per request

### Agent 3: Tax Calculator
- Model: `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo`
- Provider: TogetherAI

---

## Architecture Comparison

### Cost & Performance

| Factor | Pure Gemini | Hybrid (Current) | Pure TogetherAI |
|--------|-------------|------------------|-----------------|
| Vision Processing | Native | Native (Gemini) | Requires OCR |
| Token Limit | 2.3M | 2.3M | 131K |
| HEIC Support | Direct | Direct | Requires conversion |
| Reasoning Quality | Good | Superior (70B models) | Superior |
| Cost per Receipt | $0.0015 | $0.0008 (47% savings) | N/A |
| Processing Time | ~15s | ~19s | N/A |

### Provider Selection

**Use Gemini for:**
- Image processing (HEIC, PNG, JPG)
- Large files (>500KB)
- Multi-page PDFs
- Handwritten receipts

**Use TogetherAI for:**
- Tax law reasoning (70B models)
- Mathematical validation
- Rule-based categorization
- Cost optimization (text-only tasks)

---

## Multi-Agent Orchestration

### Consensus Mechanism
The orchestrator processes receipts through four stages:
1. Extract data (Gemini vision + phi-2 validation)
2. Categorize (Llama 3.3 70B tax reasoning)
3. Validate taxes (Llama 3.1 70B calculations)
4. Calculate consensus with weighted scores:
   - Extraction: 40% weight
   - CRA rules: 35% weight
   - Tax validation: 25% weight

---

## Configuration

### Environment Variables

```env
# QuickBooks OAuth
QB_CLIENT_ID=your_client_id
QB_CLIENT_SECRET=your_client_secret
QB_REDIRECT_URI=http://localhost:8000/callback
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com

# Gemini AI (Vision Processing)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT=30

# TogetherAI (Agent Reasoning)
TOGETHER_API_KEY=your_together_api_key
TOGETHER_MODEL_NAME=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
TOGETHER_API_URL=https://api.together.xyz/v1

# Agent Configuration
ENABLE_MULTI_AGENT=true
AGENT_LOGGING_LEVEL=INFO
AGENT_CONSENSUS_THRESHOLD=0.7
```

---

## Data Flow Comparison

### Without Agents (Original)
- Processing: ~5-8s
- Cost: $0.0015 per receipt
- Accuracy: ~85%

### With Agents (Current)
- Processing: ~19s
- Cost: $0.0008 per receipt (47% cheaper)
- Accuracy: ~90%+

---

## API Endpoints

### Multi-Agent Processing
```bash
POST /api/v1/receipts/process-file
```

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "file=@receipt.heic" \
  -F "use_agents=true" \
  -F "additional_context=Business lunch with client"
```

**Response Structure:**
- `extraction_result`: Vendor, amount, confidence
- `cra_analysis`: Category, deductibility, ITA section, audit risk
- `tax_validation`: Validation result, discrepancies, deductible amount
- `consensus`: Final category, confidence, processing time


## Structured Logging System

### AG2 Native Integration
- SQLite conversation history (7-year CRA compliance)
- Performance analytics (token usage, cost tracking)
- Correlation IDs across entire pipeline
- Real-time monitoring via API endpoints
- WebSocket support for live monitoring

**Monitoring Endpoints:**
```bash
GET /api/v1/monitoring/stats
GET /api/v1/monitoring/conversations/{correlation_id}
GET /api/v1/monitoring/performance
```

---

## Architecture Rationale

### Why Not Pure TogetherAI?
- No native vision models
- Would require OCR (2-step process)
- 131K token limit insufficient for large images
- Gemini handles HEIC with 2.3M token limit

### Why Not Pure Gemini?
- More expensive
- 70B models (Llama 3.3) superior for legal reasoning
- Less explainable (no agent breakdown)
- No consensus mechanism

### Why 3 Agents?
- Separation of concerns with specialized agents
- Transparent decision audit trail
- Consensus mechanism reduces errors
- Legal reasoning agent for CRA compliance

### Why CSV Rules?
- Non-developer updates (accountants can edit)
- Version control for rule changes
- Clear mapping to T2125 form
- Audit trail for CRA compliance

---

## Usage

### CLI
```bash
# Process with agents (default)
uv run quickexpense upload receipt.heic

# Process without agents (legacy mode)
uv run quickexpense upload receipt.heic --no-agents
```

### API
```bash
# Start server
uv run fastapi dev src/quickexpense/main.py

# Process with agents
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "file=@receipt.heic" \
  -F "use_agents=true"
```

---

## Dependencies

### Core Dependencies
- `google-generativeai >= 0.3.0` (Gemini vision)
- `pydantic ^2.5.0`

### Multi-Agent System
- `pyautogen ^0.2.0` (AG2 framework)
- `ag2[gemini] ^0.2.0` (Gemini support)
- `pandas ^2.0.0` (CSV business rules)
- `together ^1.0.0` (TogetherAI SDK)

### Monitoring & Logging
- `pandas-stubs ^2.0.0` (type hints)
