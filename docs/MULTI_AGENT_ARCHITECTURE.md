# Multi-Agent Architecture in Docker

## 🤖 Overview

QuickExpense uses a sophisticated 2-agent system powered by AG2 (AutoGen) to process receipts with Canadian tax compliance. This document explains how the multi-agent system works within the Docker container, including agent coordination, LLM integration, and consensus mechanisms.

**Latest Update (2025-10-30):** Consolidated from 3-agent to 2-agent system by integrating tax calculations into CRArulesAgent. Added GST/tip line item normalization for improved accuracy.

## 📋 Table of Contents

- [Agent Architecture](#agent-architecture)
- [Agent Responsibilities](#agent-responsibilities)
- [LLM Provider Integration](#llm-provider-integration)
- [Consensus Mechanisms](#consensus-mechanisms)
- [Docker-Specific Considerations](#docker-specific-considerations)
- [Configuration](#configuration)
- [Monitoring & Logging](#monitoring--logging)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Agent Architecture

### System Overview
```
Receipt Input (Image/PDF)
         ↓
    [DataExtractionAgent] ──── Gemini AI (Image Processing)
         ↓
         │ (Tax/Tip Normalization)
         ↓
    [CRArulesAgent] ──────── TogetherAI (Tax Rules + Calculations)
         ↓
    Orchestrator Formatting
         ↓
    Final Expense Data → QuickBooks
```

**Key Features:**
- **Line-Item Processing:** Each receipt line processed separately (no aggregation)
- **Tax Normalization:** Automatic GST/HST and tip line item creation
- **Integrated Calculations:** Tax calculations performed within CRArulesAgent
- **Category Constraints:** ALLOWED_CATEGORIES prevents LLM hallucinations

### Agent Orchestrator
The `MultiAgentOrchestrator` coordinates all agents and manages the processing pipeline:

```python
# Container endpoint: /api/v1/receipts/process-file
@router.post("/receipts/process-file")
async def process_receipt_file(
    receipt: UploadFile,
    orchestrator: MultiAgentOrchestratorDep,
    additional_context: str = "Business expense receipt"
) -> MultiAgentReceiptResponse
```

### Agent Communication Flow
1. **Sequential Processing**: Agents process data in sequence, each building on previous results
2. **Shared Context**: All agents have access to the original receipt and accumulated findings
3. **Consensus Building**: Final results require agreement or majority consensus
4. **Error Handling**: Failed agents don't block the entire pipeline

---

## 🎯 Agent Responsibilities

### 1. DataExtractionAgent
**Purpose**: Extract raw data from receipt images and PDFs using computer vision

**LLM Provider**: Gemini AI (optimized for vision tasks)

**Responsibilities**:
- Parse receipt images (JPEG, PNG, HEIC, PDF)
- Extract basic transaction data (vendor, date, amounts)
- Identify line items and tax information
- Handle multiple currencies and formats
- Validate extracted data for completeness

**Input Processing**:
```python
# Supports multiple formats
supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif', '.pdf']

# Processing pipeline
receipt_data = await data_extraction_agent.process_receipt(
    image_data=file_content,
    file_type=file_extension,
    additional_context=context
)
```

**Output Schema**:
```json
{
  "vendor_name": "Tim Hortons",
  "transaction_date": "2024-01-15",
  "total_amount": 12.45,
  "subtotal": 11.05,
  "tax_amount": 1.40,
  "currency": "CAD",
  "line_items": [...],
  "confidence_score": 0.95
}
```

### 2. CRArulesAgent
**Purpose**: Apply Canadian Revenue Agency tax rules and categorization

**LLM Provider**: TogetherAI (optimized for reasoning)

**Responsibilities**:
- Apply ITA (Income Tax Act) compliance rules
- Categorize expenses per CRA guidelines
- Determine deductibility percentages
- Identify audit risk factors
- Apply vendor-specific rules from business rules CSV

**Business Rules Integration**:
```python
# Loads from container path: /home/user/app/config/cra_rules.csv
business_rules = load_business_rules("config/cra_rules.csv")

# Vendor-aware categorization
if vendor_pattern_matches(vendor_name, rule.vendor_patterns):
    category = rule.actions.category
    confidence_boost = rule.actions.confidence_boost
```

**Key Rules Applied**:
- **ITA Section 67.1**: Meals & Entertainment (50% deductible)
- **ITA Section 18(1)(a)**: Business purpose requirement
- **GST/HST Input Tax Credits**: Proper documentation requirements
- **Travel Expenses**: Per-diem vs actual expense rules

**Output Schema**:
```json
{
  "category": "Meals & Entertainment",
  "qb_account": "Meals and Entertainment",
  "deductibility_percentage": 50.0,
  "ita_section": "ITA 67.1",
  "audit_risk": "medium",
  "compliance_notes": [...],
  "confidence_score": 0.88
}
```

### 3. TaxCalculatorAgent
**Purpose**: Validate tax calculations and GST/HST compliance

**LLM Provider**: TogetherAI (mathematical reasoning)

**Responsibilities**:
- Validate GST/HST calculations
- Calculate deductible amounts
- Verify tax rates by province/territory
- Identify discrepancies in tax amounts
- Generate final expense totals

**Tax Validation Logic**:
```python
# Provincial tax rates (embedded in container)
GST_RATE = 0.05  # Federal GST
provincial_rates = {
    "ON": 0.08,   # Ontario HST (13% total)
    "BC": 0.07,   # BC PST (12% total)
    "AB": 0.00,   # Alberta (5% GST only)
    # ... other provinces
}

# Validation checks
calculated_tax = subtotal * (gst_rate + provincial_rate)
tax_variance = abs(receipt_tax - calculated_tax)
```

**Output Schema**:
```json
{
  "calculated_gst_hst": 1.40,
  "deductible_amount": 6.23,
  "tax_validation_result": "valid",
  "variance_amount": 0.02,
  "provincial_rate": 0.13,
  "confidence_score": 0.93
}
```

---

## 🔌 LLM Provider Integration

### Hybrid LLM Strategy
The system uses a hybrid approach optimizing for both cost and performance:

**Gemini AI** (Image Processing):
- **Use Case**: DataExtractionAgent vision tasks
- **Strengths**: Excellent image understanding, HEIC/PDF support
- **Model**: gemini-2.0-flash-exp
- **Cost**: ~$0.002 per image

**TogetherAI** (Reasoning Tasks):
- **Use Case**: CRArulesAgent and TaxCalculatorAgent
- **Strengths**: Fast inference, good reasoning, cost-effective
- **Model**: meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
- **Cost**: ~$0.0008 per 1K tokens

### Provider Configuration in Container
```bash
# Environment variables
LLM_PROVIDER=together              # Primary provider
LLM_FALLBACK_ENABLED=true         # Auto-fallback enabled

# Gemini settings
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT=30

# TogetherAI settings
TOGETHER_API_KEY=your_together_key
TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
TOGETHER_MAX_TOKENS=4096
TOGETHER_TEMPERATURE=0.2
```

### Fallback Mechanism
```python
# Automatic provider fallback
try:
    result = await together_client.generate(prompt)
except (APIError, TimeoutError):
    logger.warning("TogetherAI failed, falling back to Gemini")
    result = await gemini_client.generate(prompt)
```

---

## 🤝 Consensus Mechanisms

### Consensus Types
1. **Unanimous**: All agents must agree (high confidence)
2. **Majority**: 2+ out of 3 agents agree (medium confidence)
3. **Best Effort**: Use highest confidence result (low confidence)
4. **Failure**: All agents failed (error state)

### Confidence Scoring
```python
def calculate_overall_confidence(agent_results):
    if all(agent.success for agent in agent_results):
        # Unanimous success - weighted average
        weights = [0.4, 0.35, 0.25]  # Data, Rules, Tax
        return sum(w * agent.confidence for w, agent in zip(weights, agent_results))
    elif sum(agent.success for agent in agent_results) >= 2:
        # Majority consensus
        successful_agents = [a for a in agent_results if a.success]
        return sum(a.confidence for a in successful_agents) / len(successful_agents) * 0.8
    else:
        # Failure or single success
        return max(a.confidence for a in agent_results if a.success) * 0.6
```

### Validation Rules
```python
# Cross-agent validation
def validate_consensus(agent_results):
    data_result = agent_results[0]  # DataExtractionAgent
    rules_result = agent_results[1]  # CRArulesAgent
    tax_result = agent_results[2]    # TaxCalculatorAgent

    # Amount consistency check
    if abs(data_result.total_amount - tax_result.calculated_total) > 0.10:
        add_flag("Amount discrepancy between extraction and calculation")

    # Category consistency check
    if data_result.suggested_category != rules_result.final_category:
        add_flag("Category disagreement between agents")
```

---

## 🐳 Docker-Specific Considerations

### Container Resource Requirements
```bash
# Recommended container resources
docker run \
  --memory=2g \          # 2GB RAM for LLM processing
  --cpus=1.0 \          # 1 CPU core minimum
  --shm-size=512m \     # Shared memory for model loading
  quickexpense:latest
```

### AG2 Dependencies in Container
The container includes all required AG2 components:
```dockerfile
# Key dependencies from requirements.txt
ag2[together]==0.9.9      # AG2 with TogetherAI integration
ag2[gemini]==0.9.9        # AG2 with Gemini integration
google-generativeai==0.8.5
together==1.5.26
aiohttp==3.12.15          # Async HTTP for API calls
diskcache==5.6.3          # Agent memory caching
```

### Agent State Persistence
```python
# Agents maintain state in container filesystem
/home/user/app/data/
├── agent_logs.db          # AG2 runtime logs
├── conversation_history.db # Agent conversations
└── agent_cache/           # Temporary agent cache
```

### Network Configuration
```bash
# Ensure API access for LLM providers
# Container needs outbound HTTPS (443) access to:
# - generativelanguage.googleapis.com (Gemini)
# - api.together.xyz (TogetherAI)
# - sandbox-quickbooks.api.intuit.com (QuickBooks)
```

---

## ⚙️ Configuration

### Agent-Specific Settings
```bash
# AG2 Logging in container
ENABLE_AG2_LOGGING=true
ENABLE_RUNTIME_LOGGING=true
ENABLE_CONVERSATION_LOGGING=true

# Agent behavior
AG2_TRACE_LEVEL=DEBUG
AG2_EVENT_LEVEL=INFO
LOG_AGENT_REASONING=true
LOG_INTER_AGENT_COMMUNICATION=true

# Performance settings
PERFORMANCE_SAMPLING_RATE=1.0
LOG_TOKEN_USAGE=true
```

### Business Rules Configuration
```bash
# Business rules are embedded in container at build time
# Located at: /home/user/app/config/cra_rules.csv
# Can be overridden by mounting custom rules:
docker run -v /path/to/custom_rules.csv:/home/user/app/config/cra_rules.csv quickexpense
```

### Custom Business Rules Format
```csv
id,priority,name,description_keywords,vendor_patterns,category,qb_account,deductibility_percentage,ita_section,confidence_boost
hotel_marketing,110,"Hotel Marketing Fees","marketing fee,resort fee","*hotel*,*marriott*",Travel-Lodging,Travel - Lodging,100,ITA 8(1)(f),0.2
```

---

## 📊 Monitoring & Logging

### Agent Performance Metrics
```bash
# Access runtime metrics
curl http://localhost:8000/api/v1/system/metrics

# Response includes:
{
  "agent_performance": {
    "DataExtractionAgent": {
      "success_rate": 0.95,
      "avg_processing_time": 1.2,
      "total_processed": 150
    },
    "CRArulesAgent": {
      "success_rate": 0.88,
      "avg_processing_time": 0.8,
      "total_processed": 150
    },
    "TaxCalculatorAgent": {
      "success_rate": 0.93,
      "avg_processing_time": 0.4,
      "total_processed": 150
    }
  }
}
```

### Log Collection
```bash
# Export agent logs from container
docker exec quickexpense-container tar czf - /data/agent_logs.db | cat > agent_logs.tar.gz

# View real-time agent activity
docker logs -f quickexpense-container | grep "Agent\|consensus\|processing"
```

### Structured Logging Format
```json
{
  "timestamp": "2024-01-15T10:30:15Z",
  "level": "INFO",
  "component": "MultiAgentOrchestrator",
  "correlation_id": "req_abc123",
  "event": "agent_processing_complete",
  "agent_name": "DataExtractionAgent",
  "processing_time": 1.234,
  "confidence_score": 0.95,
  "tokens_used": 1250,
  "cost": 0.002
}
```

---

## 🔧 Troubleshooting

### Common Agent Issues

#### 1. DataExtractionAgent Failures
```bash
# Check image format support
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@test.jpg" | jq '.agent_results[0].error_message'

# Common issues:
# - "Unable to detect file type" → Unsupported format
# - "Gemini API key invalid" → Check GEMINI_API_KEY
# - "Image too large" → Resize image or increase timeout
```

#### 2. CRArulesAgent Failures
```bash
# Check business rules loading
docker exec quickexpense cat /home/user/app/config/cra_rules.csv | head -5

# Common issues:
# - "Business rules file not found" → Mount config volume
# - "TogetherAI rate limited" → Check API quotas
# - "Invalid rule format" → Validate CSV structure
```

#### 3. TaxCalculatorAgent Failures
```bash
# Check tax calculation logic
curl -X POST http://localhost:8000/api/v1/test-tax-calculation \
  -d '{"subtotal": 10.00, "province": "ON"}'

# Common issues:
# - "Unknown tax rate" → Missing province configuration
# - "Calculation timeout" → Increase TOGETHER_TIMEOUT
# - "Math validation failed" → Check input data quality
```

### Agent Communication Issues
```bash
# Check agent orchestration
docker exec quickexpense tail -f /data/agent_logs.db

# Look for:
# - "Agent communication timeout"
# - "Consensus failed - no majority"
# - "Inter-agent validation errors"
```

### Performance Optimization
```bash
# Monitor resource usage during agent processing
docker stats quickexpense

# Optimize for heavy usage:
docker run --memory=4g --cpus=2.0 quickexpense  # More resources
docker run -e TOGETHER_MAX_TOKENS=2048 quickexpense  # Reduce token usage
docker run -e PERFORMANCE_SAMPLING_RATE=0.1 quickexpense  # Reduce logging
```

### Debug Mode
```bash
# Enable verbose agent logging
docker run \
  -e DEBUG=true \
  -e AG2_TRACE_LEVEL=DEBUG \
  -e LOG_AGENT_REASONING=true \
  -e LOG_INTER_AGENT_COMMUNICATION=true \
  quickexpense:latest
```

---

## 🚀 Advanced Usage

### Custom Agent Configuration
```python
# Example: Custom agent timeout configuration
# In container environment variables:
AGENT_TIMEOUT_SECONDS=60
MAX_RETRY_ATTEMPTS=3
CONSENSUS_TIMEOUT_SECONDS=30
```

### Batch Processing
```bash
# Process multiple receipts
for receipt in receipts/*.jpg; do
  curl -X POST http://localhost:8000/api/v1/receipts/process-file \
    -F "receipt=@$receipt" \
    -F "additional_context=Batch processing" \
    --output "results/$(basename $receipt .jpg).json"
done
```

### Integration with External Systems
```python
# Webhook integration for agent results
webhook_url = "https://your-system.com/expense-webhook"

agent_result = await orchestrator.process_receipt(receipt_data)
if agent_result.success and agent_result.overall_confidence > 0.8:
    await notify_webhook(webhook_url, agent_result)
```

---

## 📚 Related Documentation

- [Docker Usage Guide](./DOCKER_USAGE.md)
- [Dependencies Guide](./DEPENDENCIES.md)
- [API Reference](./API_REFERENCE.md)
- [Canadian Tax Compliance](./CRA_COMPLIANCE.md)
