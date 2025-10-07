# QuickExpense Docker Documentation

## 📚 Overview

Welcome to the comprehensive documentation for QuickExpense Docker deployment. This documentation covers everything you need to know about building, deploying, and managing the QuickExpense multi-agent receipt processing system in Docker containers.

## 🎯 What is QuickExpense?

QuickExpense is an AI-powered receipt processing system designed specifically for Canadian small businesses and sole proprietors. It features:

- **Multi-Agent AI System**: 3 specialized agents for accurate data extraction and Canadian tax compliance
- **QuickBooks Integration**: Direct expense creation in QuickBooks Online
- **Canadian Tax Compliance**: Built-in CRA rules and ITA compliance
- **Multiple File Formats**: Support for JPEG, PNG, PDF, HEIC (iPhone photos)
- **Modern Web Interface**: Clean, responsive UI for easy receipt processing

## 📋 Documentation Index

### 🚀 Getting Started
- **[Docker Usage Guide](./DOCKER_USAGE.md)** - Complete guide to building and running QuickExpense in Docker
- **[Hugging Face Deployment](./HUGGING_FACE_DEPLOYMENT.md)** - Step-by-step deployment to Hugging Face Spaces

### 🏗️ Architecture & Technical Details
- **[Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)** - How the 3-agent system works in Docker
- **[Dependencies Guide](./DEPENDENCIES.md)** - All dependencies, versions, and their purposes
- **[API Reference](./API_REFERENCE.md)** - Complete API documentation with examples

### 📊 Additional Resources
- **[Docker Deployment Plan](./DOCKER_DEPLOYMENT.md)** - Original implementation plan and status

## 🏃 Quick Start

### For Immediate Usage
```bash
# 1. Clone and build
git clone <repository-url>
cd quickExpense
docker build -t quickexpense:latest .

# 2. Run with your API keys
docker run -d \
  --name quickexpense \
  -p 8000:7860 \
  -v $(pwd)/data:/data \
  -e QB_CLIENT_ID="your_quickbooks_client_id" \
  -e QB_CLIENT_SECRET="your_quickbooks_client_secret" \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -e TOGETHER_API_KEY="your_together_api_key" \
  quickexpense:latest

# 3. Access the application
open http://localhost:8000
```

### For Hugging Face Spaces Deployment
1. Follow the **[Hugging Face Deployment Guide](./HUGGING_FACE_DEPLOYMENT.md)**
2. Set up your API keys as HF Secrets
3. Push to your space repository
4. Access at `https://YOUR_USERNAME-quickexpense-app.hf.space`

## 🔧 Key Features

### Multi-Agent Processing Pipeline
```
Receipt Upload → DataExtractionAgent → CRArulesAgent → TaxCalculatorAgent → QuickBooks
                      ↓                    ↓                ↓              ↓
                  Image OCR        Canadian Tax Rules   Tax Validation   Expense Creation
                  (Gemini AI)      (TogetherAI)        (TogetherAI)     (QB API)
```

### Supported File Formats
- **Images**: JPEG, PNG, GIF, BMP, WEBP
- **iPhone Photos**: HEIC, HEIF (native support)
- **Documents**: PDF (multi-page supported)

### Canadian Tax Compliance
- **ITA Section 67.1**: Meals & Entertainment (50% deductible)
- **GST/HST Calculations**: Provincial tax rate validation
- **CRA Audit Risk Assessment**: Risk scoring for compliance
- **Business Rules Engine**: Vendor-aware categorization

## 🏗️ Architecture Overview

### Container Structure
```
quickexpense:latest (1.01GB optimized)
├── Python 3.12 Runtime
├── FastAPI Application (Port 7860)
├── Multi-Agent System (AG2/AutoGen)
├── LLM Providers (Gemini + TogetherAI)
├── Image Processing (Pillow + HEIC support)
├── QuickBooks Integration
└── Persistent Storage (/data)
```

### Key Components
- **Base Image**: `python:3.12-slim`
- **Non-root User**: UID 1000 (HF Spaces compliant)
- **Health Checks**: Built-in monitoring
- **Persistent Storage**: Volume mounting for tokens and logs
- **Environment Config**: Extensive environment variable support

## 📊 Performance & Specifications

### Resource Requirements
- **CPU**: 1 core minimum, 2 cores recommended
- **Memory**: 2GB minimum, 4GB for heavy usage
- **Storage**: 10GB for application + data
- **Network**: Outbound HTTPS for API calls

### Processing Performance
- **Image Processing**: ~1-2 seconds per receipt
- **Multi-Agent Processing**: ~2-4 seconds total
- **Cost Optimization**: 47% cost reduction vs pure Gemini
- **Accuracy**: 92%+ consensus confidence typical

## 🔐 Security & Compliance

### Security Features
- Non-root container execution
- Environment variable secrets management
- API key validation and rotation support
- Audit logging for CRA compliance
- 7-year log retention policy

### Canadian Tax Compliance
- **CRA ITA Compliance**: Automated section identification
- **Business Rules Engine**: 50+ built-in rules
- **Audit Trail**: Complete processing history
- **GST/HST Validation**: Provincial rate compliance
- **Deductibility Calculations**: Automatic percentage application

## 🔗 Integration Points

### QuickBooks Online
- OAuth 2.0 authentication
- Purchase/Expense creation
- Vendor management
- Account categorization
- Token refresh automation

### AI Services
- **Gemini AI**: Image processing and OCR
- **TogetherAI**: Tax reasoning and calculations
- **Hybrid Strategy**: Cost optimization through provider selection
- **Fallback Support**: Automatic provider switching

## 📈 Monitoring & Analytics

### Built-in Monitoring
- Health check endpoints
- Processing time metrics
- Agent performance tracking
- API usage analytics
- Error rate monitoring

### Logging
- Structured JSON logs
- Agent conversation history
- CRA compliance audit trail
- Performance metrics
- Cost tracking per transaction

## 🚀 Deployment Options

### Local Development
- Docker with hot-reload
- Direct Python execution
- Development environment variables
- Local QuickBooks sandbox

### Production Cloud
- **Hugging Face Spaces**: Free tier available
- **Custom Infrastructure**: Full Docker support
- **Kubernetes**: Scalable deployment
- **Cloud Providers**: AWS, GCP, Azure compatible

## 🔧 Customization

### Business Rules
- CSV-based rules engine
- Vendor-specific categorization
- Custom deductibility rules
- Province-specific tax rates
- Audit risk factors

### Agent Configuration
- LLM provider selection
- Model parameter tuning
- Consensus thresholds
- Timeout configurations
- Retry logic settings

## 📞 Support & Contributing

### Getting Help
1. **Check Documentation**: Start with relevant guides above
2. **Review Examples**: API reference includes usage examples
3. **Troubleshooting**: Each guide includes troubleshooting sections
4. **GitHub Issues**: Report bugs and request features

### Contributing
- **Bug Reports**: Use GitHub issues
- **Feature Requests**: Discuss in issues first
- **Pull Requests**: Follow conventional commits
- **Documentation**: Help improve these guides

## 📚 Documentation Hierarchy

```
docs/
├── README.md                      # This overview (start here)
├── DOCKER_USAGE.md               # Complete Docker guide
├── HUGGING_FACE_DEPLOYMENT.md    # HF Spaces deployment
├── MULTI_AGENT_ARCHITECTURE.md   # Agent system details
├── DEPENDENCIES.md               # All dependencies explained
├── API_REFERENCE.md              # Complete API documentation
└── DOCKER_DEPLOYMENT.md          # Implementation plan & status
```

### Recommended Reading Order

**For Users**:
1. This overview (README.md)
2. [Docker Usage Guide](./DOCKER_USAGE.md)
3. [Hugging Face Deployment](./HUGGING_FACE_DEPLOYMENT.md)
4. [API Reference](./API_REFERENCE.md)

**For Developers**:
1. [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)
2. [Dependencies Guide](./DEPENDENCIES.md)
3. [Docker Usage Guide](./DOCKER_USAGE.md)
4. [API Reference](./API_REFERENCE.md)

## 🎉 What's Next?

1. **Start with [Docker Usage Guide](./DOCKER_USAGE.md)** for local development
2. **Deploy to [Hugging Face Spaces](./HUGGING_FACE_DEPLOYMENT.md)** for production
3. **Explore [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)** to understand the AI system
4. **Reference [API Documentation](./API_REFERENCE.md)** for integration

---

*Last updated: January 2025*
*QuickExpense Docker v1.0 - Production Ready*
