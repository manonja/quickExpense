# Hybrid LLM Implementation: Gemini + TogetherAI

## Overview

QuickExpense uses a hybrid approach combining Gemini's superior image processing capabilities with TogetherAI's cost-effective text reasoning. This architecture was necessitated by token limitations in TogetherAI (131K limit) when processing large images like HEIC files (2.3M+ tokens).

## Architecture

### LLM Provider Layer

```
quickexpense/services/llm_provider.py
├── BaseLLMProvider (Abstract)
├── GeminiProvider
├── TogetherAIProvider
└── LLMProviderFactory
```

### Agent Configuration

1. **DataExtractionAgent**
   - Primary: GeminiService for image extraction
   - Secondary: TogetherAI for validation (optional)

2. **CRArulesAgent**
   - Uses configured provider (TogetherAI by default)

3. **TaxCalculatorAgent**
   - Uses configured provider (TogetherAI by default)

## Configuration

### Environment Variables

```bash
# LLM Provider Settings
LLM_PROVIDER=together  # Options: together, gemini, auto
LLM_FALLBACK_ENABLED=true

# TogetherAI Configuration
TOGETHER_API_KEY=your_key
TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
TOGETHER_MAX_TOKENS=4096
TOGETHER_TEMPERATURE=0.2

# Gemini Configuration (for image processing)
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.0-flash-exp
```

## Implementation Details

### Image Processing Flow

1. **Receipt Upload** → Base64 encoding
2. **File Type Detection** → Magic bytes checking
3. **Gemini Processing**:
   ```python
   # Direct image handling without base64 in prompt
   extracted_receipt = await gemini_service.extract_receipt_data(
       file_base64=file_base64,
       additional_context=context
   )
   ```
4. **TogetherAI Validation** (optional):
   ```python
   # Text-only validation of extracted data
   validated_data = await self._validate_with_agent(extracted_data)
   ```

### Provider Selection Logic

```python
class LLMProviderFactory:
    @staticmethod
    def create(settings: Settings, provider: str | None = None) -> BaseLLMProvider:
        provider = provider or settings.llm_provider

        if provider == "together":
            return TogetherAIProvider(settings)
        elif provider == "gemini":
            return GeminiProvider(settings)
        elif provider == "auto":
            # Auto-select based on context
            return TogetherAIProvider(settings)
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

### Agent Configuration

```python
# TogetherAI configuration for autogen
{
    "config_list": [{
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "api_key": settings.together_api_key,
        "api_type": "together",  # Critical for autogen
        "max_tokens": 4096,
        "temperature": 0.2,
    }],
    "cache_seed": None,  # Disable caching
}
```

## Performance Metrics

### HEIC Receipt Processing (PHO GEORGIA EXPRESS)

| Stage | Provider | Time | Notes |
|-------|----------|------|-------|
| Image Extraction | Gemini | 14.92s | 2.3M tokens handled natively |
| Data Validation | TogetherAI | 3.71s | Text-only processing |
| CRA Rules | TogetherAI | 1.21s | Rule matching |
| Tax Calculation | TogetherAI | 1.40s | Validation |
| **Total** | Hybrid | **21.23s** | 72% confidence |

### Cost Comparison

- **Gemini-only**: ~$0.15 per receipt (all agents using vision)
- **TogetherAI-only**: Token limit exceeded, cannot process
- **Hybrid**: ~$0.08 per receipt (vision + text)

## Key Benefits

1. **Capability**: Handles any image format/size via Gemini
2. **Cost**: 47% reduction vs pure Gemini approach
3. **Flexibility**: Easy provider switching via config
4. **Reliability**: Fallback support built-in
5. **Performance**: Parallel agent processing possible

## Testing

### Test Script

```bash
# Run hybrid integration test
uv run python test_together_integration.py
```

### Test Coverage

- ✅ HEIC image processing
- ✅ Provider configuration
- ✅ Agent orchestration
- ✅ Error handling
- ✅ Confidence scoring
- ✅ JSON serialization

## Future Enhancements

1. **Dynamic Provider Selection**
   - Use Gemini for complex receipts
   - Use TogetherAI for simple text receipts

2. **Caching Layer**
   - Cache Gemini extractions
   - Reuse for agent validation

3. **Model Selection**
   - Different models for different tasks
   - A/B testing framework

4. **Performance Optimization**
   - Parallel agent execution
   - Streaming responses

## Troubleshooting

### Common Issues

1. **Token Limit Errors**
   - Symptom: "inputs tokens + max_new_tokens must be <= 131073"
   - Solution: Ensure images go through Gemini, not TogetherAI

2. **JSON Serialization**
   - Symptom: "Object of type date is not JSON serializable"
   - Solution: Use `model_dump(mode="json")` for Pydantic models

3. **Provider Not Found**
   - Symptom: "Unknown provider: xyz"
   - Solution: Check LLM_PROVIDER env var spelling

### Debug Commands

```bash
# Check provider configuration
grep "LLM_PROVIDER\|TOGETHER\|GEMINI" .env

# View processing logs
tail -f test_together.log

# Test individual agents
uv run python -m quickexpense.services.agents.data_extraction_agent
```
