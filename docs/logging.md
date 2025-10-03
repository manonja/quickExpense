# Structured Logging for QuickExpense

Comprehensive logging system for the multi-agent receipt processing pipeline with AG2/AutoGen integration.

## Overview

The logging system provides full observability into the agent decision-making process, tracking confidence scores, inter-agent communication, and performance metrics while maintaining CRA compliance.

## Quick Start

### 1. Enable Logging

```bash
# Add to .env file
ENABLE_AG2_LOGGING=true
ENABLE_CONVERSATION_LOGGING=true
ENABLE_PERFORMANCE_MONITORING=true
LOG_AGENT_REASONING=true
```

### 2. Run with Logging

```bash
# Process receipts with full logging
uv run quickexpense upload receipt.jpg

# View logs in real-time
tail -f data/conversation_history.db
```

### 3. Monitor Performance

```bash
# Start server
uv run fastapi dev src/quickexpense/main.py

# View monitoring dashboard
open http://localhost:8000/docs#/monitoring
```

## Key Components

### AG2 Structured Logger
- Tracks agent decisions with confidence scores
- Logs inter-agent communication
- Records consensus decision making
- Integrates with AG2's native logging

### Conversation History
- SQLite storage of complete processing flows
- Searchable by correlation ID, agent, or date
- 7-year retention for CRA compliance

### Performance Analytics
- Real-time metrics per agent
- Token usage and cost tracking
- Error pattern analysis
- Confidence trend monitoring

## Developer Workflow

### 1. Processing with Correlation ID

```python
from quickexpense.services.logging_integration import create_logging_integration

# Create logging context
logging = create_logging_integration(correlation_id="expense-12345")

# Process receipt with full logging
orchestrator = logging.create_logging_orchestrator(
    data_agent, cra_agent, tax_agent
)
result = await orchestrator.process_receipt(file_base64)
```

### 2. Querying Logs

```python
# Get conversation history
conversation = logging.conversation_logger.get_conversation("expense-12345")

# Get performance metrics
stats = logging.performance_analytics.get_agent_performance("DataExtractionAgent")
print(f"Success rate: {stats.success_rate:.2%}")
```

### 3. API Monitoring

```bash
# System performance
GET /api/v1/monitoring/performance?hours=24

# Agent-specific metrics
GET /api/v1/monitoring/agents/CRArulesAgent/performance

# Recent conversations
GET /api/v1/monitoring/conversations?limit=10

# Token usage report
GET /api/v1/monitoring/token-usage?group_by=model
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_AG2_LOGGING` | true | Enable AG2/AutoGen native logging |
| `ENABLE_CONVERSATION_LOGGING` | true | Store conversation history |
| `ENABLE_PERFORMANCE_MONITORING` | true | Track performance metrics |
| `LOG_AGENT_REASONING` | true | Log detailed agent thought process |
| `LOG_TOKEN_USAGE` | true | Track LLM token costs |
| `AG2_TRACE_LEVEL` | DEBUG | AG2 trace logger level |
| `LOGGING_DB_PATH` | data/agent_logs.db | AG2 runtime database |
| `CONVERSATION_DB_PATH` | data/conversation_history.db | Conversation storage |

## Database Schema

### Conversations Table
- `correlation_id` - Unique identifier for request
- `session_id` - AG2 session identifier
- `start_time`, `end_time` - Processing timestamps
- `final_result` - JSON with consensus data

### Conversation Entries Table
- `agent_name` - Which agent generated entry
- `role` - user/assistant/system
- `content` - Message content
- `confidence_score` - Agent confidence (0-1)
- `processing_time` - Time taken in seconds

## Testing

```bash
# Run comprehensive logging test
uv run python test_logging_integration.py

# Output locations:
# - test_logging_integration.log
# - data/conversation_history.db
# - data/agent_logs.db
```

## Example Output

```json
{
  "correlation_id": "expense-12345",
  "overall_confidence": 0.85,
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "confidence_score": 0.95,
      "processing_time": 2.34,
      "success": true
    },
    {
      "agent_name": "CRArulesAgent",
      "confidence_score": 0.80,
      "processing_time": 0.45,
      "category": "Meals & Entertainment",
      "audit_risk": "MEDIUM"
    }
  ],
  "consensus_decision": {
    "method": "simple_average",
    "final_category": "Meals & Entertainment",
    "deductibility": 50,
    "flags_for_review": ["Low confidence score (0.75 < 0.80)"]
  }
}
```

## Performance Impact

- Minimal overhead: <5% processing time increase
- Async writes to avoid blocking
- Configurable sampling rate for high-volume scenarios
- SQLite for efficient local storage
