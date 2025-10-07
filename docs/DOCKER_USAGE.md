# Docker Usage Guide for QuickExpense

## 🐳 Overview

This guide covers how to build, run, and deploy the QuickExpense Docker container. The container includes a complete FastAPI application with multi-agent receipt processing, QuickBooks integration, and Canadian tax compliance features.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Building the Container](#building-the-container)
- [Running Locally](#running-locally)
- [Environment Variables](#environment-variables)
- [Volume Mounting](#volume-mounting)
- [Health Checks](#health-checks)
- [API Usage](#api-usage)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Prerequisites
- Docker installed and running
- API keys for QuickBooks, Gemini AI, and TogetherAI

### 1. Build the Container
```bash
# Clone the repository
git clone <repository-url>
cd quickExpense

# Build the optimized Docker image
docker build -t quickexpense:latest .
```

### 2. Run with Environment Variables
```bash
docker run -d \
  --name quickexpense \
  -p 8000:7860 \
  -v $(pwd)/data:/data \
  -e QB_CLIENT_ID="your_quickbooks_client_id" \
  -e QB_CLIENT_SECRET="your_quickbooks_client_secret" \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -e TOGETHER_API_KEY="your_together_api_key" \
  quickexpense:latest
```

### 3. Access the Application
- **Web UI**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 🔨 Building the Container

### Standard Build
```bash
docker build -t quickexpense:latest .
```

### Optimized Build (Recommended)
```bash
# Build with optimizations for smaller image size
docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --progress=plain \
  -t quickexpense:optimized .
```

### Build Arguments
The Dockerfile supports several build-time optimizations:
- Uses multi-stage caching for faster rebuilds
- Combines RUN commands to reduce layers
- Cleans up package caches and temporary files
- Optimizes Python bytecode compilation

### Image Size
- **Base image**: ~150MB
- **Final optimized image**: ~1.01GB
- **Includes**: Python 3.12, FastAPI, AG2/AutoGen, image processing libraries

---

## 🏃 Running Locally

### Basic Run Command
```bash
docker run -p 8000:7860 quickexpense:latest
```

### Production Run with Persistence
```bash
docker run -d \
  --name quickexpense-prod \
  --restart unless-stopped \
  -p 8000:7860 \
  -v /path/to/persistent/data:/data \
  -e QB_CLIENT_ID="$QB_CLIENT_ID" \
  -e QB_CLIENT_SECRET="$QB_CLIENT_SECRET" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e TOGETHER_API_KEY="$TOGETHER_API_KEY" \
  -e QB_REDIRECT_URI="http://localhost:8000/api/web/callback" \
  quickexpense:latest
```

### Development Run with Hot Reload
```bash
# For development - mount source code
docker run -it \
  -p 8000:7860 \
  -v $(pwd)/src:/home/user/app/src \
  -v $(pwd)/config:/home/user/app/config \
  -v $(pwd)/data:/data \
  -e QB_CLIENT_ID="$QB_CLIENT_ID" \
  -e QB_CLIENT_SECRET="$QB_CLIENT_SECRET" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e TOGETHER_API_KEY="$TOGETHER_API_KEY" \
  quickexpense:latest
```

---

## 🔧 Environment Variables

### Required Variables
```bash
# QuickBooks OAuth (Required)
QB_CLIENT_ID=your_quickbooks_client_id
QB_CLIENT_SECRET=your_quickbooks_client_secret

# AI Services (At least one required)
TOGETHER_API_KEY=your_together_api_key  # Primary LLM provider
GEMINI_API_KEY=your_gemini_api_key      # Image processing & fallback
```

### Optional Configuration
```bash
# QuickBooks Settings
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com  # or production
QB_REDIRECT_URI=http://localhost:8000/api/web/callback
QB_OAUTH_ENVIRONMENT=sandbox  # or production

# LLM Provider Configuration
LLM_PROVIDER=together         # together, gemini, or auto
LLM_FALLBACK_ENABLED=true     # Enable automatic fallback

# Gemini Configuration
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT=30

# TogetherAI Configuration
TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
TOGETHER_MAX_TOKENS=4096
TOGETHER_TEMPERATURE=0.2

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
PORT=7860

# AG2 Logging Configuration
ENABLE_AG2_LOGGING=true
ENABLE_RUNTIME_LOGGING=true
ENABLE_CONVERSATION_LOGGING=true
```

### Environment File
Create a `.env` file for easier management:
```bash
# Create .env file
cat > .env << EOF
QB_CLIENT_ID=your_quickbooks_client_id
QB_CLIENT_SECRET=your_quickbooks_client_secret
GEMINI_API_KEY=your_gemini_api_key
TOGETHER_API_KEY=your_together_api_key
EOF

# Run with env file
docker run --env-file .env -p 8000:7860 quickexpense:latest
```

---

## 💾 Volume Mounting

### Persistent Data Storage
The container uses `/data` for persistent storage:

```bash
# Mount local directory
docker run -v /host/path/data:/data quickexpense:latest

# Use Docker volume
docker volume create quickexpense-data
docker run -v quickexpense-data:/data quickexpense:latest
```

### What Gets Stored
- **tokens.json**: QuickBooks OAuth tokens
- **agent_logs.db**: Multi-agent processing logs
- **conversation_history.db**: Chat history and decisions
- **business_rules.csv**: Custom tax rules (if modified)

### Data Structure
```
/data/
├── tokens.json              # OAuth tokens (auto-created)
├── agent_logs.db           # AG2 runtime logs
├── conversation_history.db # Agent conversations
└── custom_rules.csv        # Custom business rules
```

### Backup Strategy
```bash
# Backup persistent data
docker run --rm -v quickexpense-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/quickexpense-backup.tar.gz -C /data .

# Restore persistent data
docker run --rm -v quickexpense-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/quickexpense-backup.tar.gz -C /data
```

---

## 🏥 Health Checks

### Built-in Health Checks
The container includes automated health monitoring:

```bash
# Check health status
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "service": "quickexpense"
}
```

### Docker Health Check
The Dockerfile includes a built-in health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1
```

### Health Check Commands
```bash
# View health status
docker ps  # Shows health status in STATUS column

# View detailed health logs
docker inspect --format='{{json .State.Health}}' quickexpense

# Manual health check
docker exec quickexpense curl -f http://localhost:7860/health
```

---

## 📡 API Usage

### Core Endpoints

#### 1. Health Check
```bash
curl http://localhost:8000/health
```

#### 2. API Information
```bash
curl http://localhost:8000/api/v1/
```

#### 3. Multi-Agent Receipt Processing
```bash
# Upload receipt file
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@/path/to/receipt.jpg" \
  -F "additional_context=Business meal with client"
```

#### 4. Simple Receipt Extraction
```bash
# Extract receipt data with base64
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "'$(base64 -i receipt.jpg)'",
    "category": "Travel",
    "additional_context": "Business trip to NYC"
  }'
```

### Response Examples

#### Multi-Agent Processing Response
```json
{
  "success": true,
  "overall_confidence": 0.92,
  "vendor_name": "Tim Hortons",
  "transaction_date": "2024-01-15",
  "total_amount": 12.45,
  "subtotal": 11.05,
  "tax_amount": 1.40,
  "category": "Meals & Entertainment",
  "deductibility_percentage": 50.0,
  "qb_account": "Meals and Entertainment",
  "ita_section": "ITA 67.1",
  "audit_risk": "low",
  "processing_time": 2.34,
  "consensus_method": "majority",
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "success": true,
      "confidence_score": 0.95,
      "processing_time": 1.2
    },
    {
      "agent_name": "CRArulesAgent",
      "success": true,
      "confidence_score": 0.88,
      "processing_time": 0.8
    },
    {
      "agent_name": "TaxCalculatorAgent",
      "success": true,
      "confidence_score": 0.93,
      "processing_time": 0.4
    }
  ]
}
```

### Supported File Formats
- **Images**: JPEG, PNG, GIF, BMP, WEBP
- **iPhone Photos**: HEIC, HEIF
- **Documents**: PDF (multi-page supported)

---

## 🔍 Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker logs quickexpense

# Common causes:
# - Missing required environment variables
# - Port already in use
# - Invalid API keys
```

#### 2. Permission Denied
```bash
# Ensure proper volume permissions
sudo chown -R 1000:1000 /path/to/data

# Or use named volume
docker volume create quickexpense-data
```

#### 3. API Keys Not Working
```bash
# Test environment variables
docker exec quickexpense env | grep -E "(QB_|GEMINI|TOGETHER)"

# Verify API key format
# QB_CLIENT_ID: Should be Intuit app key
# GEMINI_API_KEY: Should start with "AI"
# TOGETHER_API_KEY: Should be long alphanumeric
```

#### 4. Multi-Agent Processing Fails
```bash
# Check agent logs
curl http://localhost:8000/api/v1/system/logs

# Common issues:
# - Invalid API keys
# - Network connectivity
# - Rate limiting
```

### Debug Mode
```bash
# Run in debug mode
docker run -it \
  -e DEBUG=true \
  -e LOG_LEVEL=DEBUG \
  quickexpense:latest
```

### Log Collection
```bash
# Collect all logs
docker logs quickexpense > container.log 2>&1

# Export agent logs
docker exec quickexpense cat /data/agent_logs.db > agent_logs.db
```

### Performance Tuning
```bash
# Increase memory if needed
docker run --memory=2g quickexpense:latest

# Monitor resource usage
docker stats quickexpense
```

---

## 🚀 Production Deployment

### Docker Compose
```yaml
version: '3.8'
services:
  quickexpense:
    build: .
    ports:
      - "8000:7860"
    volumes:
      - quickexpense-data:/data
    environment:
      - QB_CLIENT_ID=${QB_CLIENT_ID}
      - QB_CLIENT_SECRET=${QB_CLIENT_SECRET}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - TOGETHER_API_KEY=${TOGETHER_API_KEY}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7860/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  quickexpense-data:
```

### Load Balancer Configuration
```nginx
upstream quickexpense {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://quickexpense;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://quickexpense/health;
        access_log off;
    }
}
```

---

## 📚 Related Documentation

- [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)
- [Dependencies Guide](./DEPENDENCIES.md)
- [Hugging Face Spaces Deployment](./HUGGING_FACE_DEPLOYMENT.md)
- [API Reference](./API_REFERENCE.md)
