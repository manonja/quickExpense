# Hugging Face Spaces Deployment Guide

## 🚀 Overview

This guide provides step-by-step instructions for deploying QuickExpense to Hugging Face Spaces using Docker. Hugging Face Spaces offers free hosting for machine learning applications with GPU acceleration and persistent storage.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Hugging Face Spaces Setup](#hugging-face-spaces-setup)
- [Environment Configuration](#environment-configuration)
- [Deployment Process](#deployment-process)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## 📚 Prerequisites

### Required Accounts
1. **Hugging Face Account**: [Create account](https://huggingface.co/join)
2. **QuickBooks Developer Account**: [Intuit Developer](https://developer.intuit.com/)
3. **AI Service APIs**:
   - **Gemini AI**: [Google AI Studio](https://aistudio.google.com/app/apikey)
   - **TogetherAI**: [Together Platform](https://api.together.xyz/)

### Required Information
- QuickBooks Client ID and Secret
- Gemini API key
- TogetherAI API key
- Your Hugging Face username

---

## 🏗️ Hugging Face Spaces Setup

### 1. Create New Space
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click **"Create new Space"**
3. Configure your space:
   ```
   Space name: quickexpense-app
   License: MIT
   Space SDK: Docker
   Space hardware: CPU basic (free tier)
   Visibility: Public or Private
   ```
4. Click **"Create Space"**

### 2. Initial Repository Setup
```bash
# Clone your new space repository
git clone https://huggingface.co/spaces/YOUR_USERNAME/quickexpense-app
cd quickexpense-app

# Copy QuickExpense files to the space
cp -r /path/to/quickexpense/* .

# Verify required files are present
ls -la
# Should include: Dockerfile, requirements.txt, src/, config/
```

### 3. Space Configuration
Create or update `README.md` in your space:
```markdown
---
title: QuickExpense AI Receipt Processor
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# QuickExpense AI Receipt Processor

AI-powered receipt processing for Canadian small businesses with QuickBooks integration.

## Features
- Multi-agent AI system for accurate data extraction
- Canadian tax compliance (CRA rules)
- QuickBooks Online integration
- Support for HEIC, PDF, and image receipts

## Usage
1. Upload a receipt image or PDF
2. Review the AI-extracted data
3. Approve to create expense in QuickBooks
```

---

## ⚙️ Environment Configuration

### 1. Set Hugging Face Secrets
In your Hugging Face Space settings, add these secrets:

**Required Secrets**:
```bash
QB_CLIENT_ID=your_quickbooks_client_id
QB_CLIENT_SECRET=your_quickbooks_client_secret
GEMINI_API_KEY=your_gemini_api_key
TOGETHER_API_KEY=your_together_api_key
```

**Optional Configuration**:
```bash
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
QB_REDIRECT_URI=https://YOUR_USERNAME-quickexpense-app.hf.space/api/web/callback
QB_OAUTH_ENVIRONMENT=sandbox
LLM_PROVIDER=together
LLM_FALLBACK_ENABLED=true
DEBUG=false
LOG_LEVEL=INFO
```

### 2. Update Dockerfile for HF Spaces
Ensure your Dockerfile includes HF-specific configuration:
```dockerfile
# Update redirect URI for production
ENV QB_REDIRECT_URI=https://USER_SPACE_NAME.hf.space/api/web/callback

# Ensure proper port configuration
EXPOSE 7860
ENV PORT=7860
```

### 3. Production vs Sandbox
For production deployment, update environment variables:
```bash
# Production QuickBooks
QB_BASE_URL=https://quickbooks.api.intuit.com
QB_OAUTH_ENVIRONMENT=production

# Update redirect URI to your actual space URL
QB_REDIRECT_URI=https://YOUR_USERNAME-quickexpense-app.hf.space/api/web/callback
```

---

## 🚀 Deployment Process

### 1. Prepare Files for Deployment
```bash
# Ensure all required files are in your space
ls -la
# Required:
# ├── Dockerfile
# ├── requirements.txt
# ├── README.md
# ├── src/
# ├── config/
# └── .gitignore (optional)

# Verify Dockerfile is optimized
grep -E "(USER user|EXPOSE 7860|PORT=7860)" Dockerfile
```

### 2. Commit and Push
```bash
# Add all files
git add .

# Commit with descriptive message
git commit -m "Initial deployment of QuickExpense to Hugging Face Spaces"

# Push to trigger deployment
git push origin main
```

### 3. Monitor Deployment
1. Go to your space on Hugging Face
2. Check the **"Logs"** tab to monitor build progress
3. Deployment typically takes 5-10 minutes

**Expected Log Output**:
```
Building Docker image...
[+] Building 120.5s (15/15) FINISHED
Successfully built abc123def456
Starting container...
Container started successfully
App is running on port 7860
```

### 4. Verify Deployment
Once deployment completes:
1. Click **"Open in Browser"** or visit your space URL
2. Test health endpoint: `https://YOUR_USERNAME-quickexpense-app.hf.space/health`
3. Access API docs: `https://YOUR_USERNAME-quickexpense-app.hf.space/docs`

---

## 🔧 Post-Deployment Configuration

### 1. QuickBooks OAuth Setup
Update your QuickBooks app settings:

1. Go to [Intuit Developer Console](https://developer.intuit.com/app/developer/myapps)
2. Select your app
3. Go to **"Keys & OAuth"**
4. Update **Redirect URIs**:
   ```
   https://YOUR_USERNAME-quickexpense-app.hf.space/api/web/callback
   ```
5. Save changes

### 2. Test OAuth Flow
1. Visit your deployed app
2. Click **"Connect to QuickBooks"**
3. Complete OAuth authorization
4. Verify tokens are saved to persistent storage

### 3. Test Receipt Processing
1. Upload a test receipt image
2. Verify multi-agent processing works
3. Check QuickBooks for created expense
4. Review logs for any issues

---

## 📊 Monitoring & Maintenance

### 1. Application Logs
Access logs through Hugging Face interface:
1. Go to your space
2. Click **"Logs"** tab
3. Monitor for errors or performance issues

### 2. Persistent Storage
Hugging Face Spaces provides persistent storage at `/data`:
```bash
# Your app data structure
/data/
├── tokens.json              # QuickBooks OAuth tokens
├── agent_logs.db           # Multi-agent processing logs
├── conversation_history.db # Agent conversation history
└── uploaded_receipts/      # Temporary receipt storage
```

### 3. Performance Monitoring
Monitor key metrics:
- Response times for receipt processing
- Multi-agent consensus rates
- API error rates
- Token refresh success

### 4. Updates and Maintenance
```bash
# Update your space
git pull origin main  # Get latest changes
# Make your updates
git add .
git commit -m "Update: description of changes"
git push origin main  # Triggers redeployment
```

---

## 🔍 Troubleshooting

### Common Deployment Issues

#### 1. Build Failures
```bash
# Check Dockerfile syntax
docker build -t quickexpense-test .

# Common issues:
# - Missing dependencies in requirements.txt
# - Incorrect file paths in COPY commands
# - System package installation failures
```

#### 2. Container Start Failures
```bash
# Check container logs in HF Spaces
# Common issues:
# - Missing required environment variables
# - Port configuration problems
# - File permission issues
```

#### 3. OAuth Redirect Issues
```bash
# Verify redirect URI matches exactly:
# HF Spaces URL: https://YOUR_USERNAME-quickexpense-app.hf.space
# OAuth redirect: /api/web/callback
# Full URL: https://YOUR_USERNAME-quickexpense-app.hf.space/api/web/callback
```

### Environment Variable Issues
```bash
# Check if secrets are properly set
# In your space logs, look for:
# - "Environment variable not found"
# - "Invalid API key format"
# - "OAuth configuration missing"
```

### Multi-Agent Processing Issues
```bash
# Common problems:
# - API rate limits (check TogetherAI/Gemini quotas)
# - Network timeouts (increase timeout values)
# - Agent initialization failures (check dependencies)
```

### Performance Issues
```bash
# If processing is slow:
# - Consider upgrading to GPU space
# - Optimize image sizes before processing
# - Implement request queuing for high load
```

---

## 🏆 Best Practices

### 1. Security
- **Never commit API keys** to git repository
- Use Hugging Face Secrets for all sensitive data
- Regularly rotate API keys
- Monitor access logs for suspicious activity

### 2. Performance
- Use **CPU basic** for light usage (free)
- Upgrade to **CPU upgraded** or **GPU** for heavy usage
- Implement caching for business rules
- Optimize images before processing

### 3. Reliability
- Set up health check monitoring
- Implement graceful error handling
- Use fallback LLM providers
- Regular backup of persistent data

### 4. Cost Management
- Monitor API usage (Gemini/TogetherAI)
- Implement request rate limiting
- Use hybrid LLM strategy (current implementation)
- Consider caching frequent operations

### 5. User Experience
- Provide clear error messages
- Show processing progress
- Implement retry mechanisms
- Add usage analytics

---

## 📈 Scaling Considerations

### 1. Traffic Growth
```bash
# Free tier limitations:
# - CPU basic: Limited concurrent users
# - No custom domain
# - Community support only

# Paid tier benefits:
# - Better performance
# - Custom domains
# - Priority support
# - Advanced analytics
```

### 2. Feature Expansion
Consider these enhancements:
- User authentication and multi-tenancy
- Batch receipt processing
- Custom business rules interface
- Integration with other accounting systems
- Mobile app support

### 3. Enterprise Deployment
For enterprise use:
- Deploy on your own infrastructure
- Implement proper user management
- Add audit logging and compliance features
- Set up monitoring and alerting
- Implement backup and disaster recovery

---

## 🔗 Space Configuration Examples

### Basic Space (Free Tier)
```yaml
# README.md frontmatter
---
title: QuickExpense Receipt Processor
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---
```

### Production Space (Paid Tier)
```yaml
# README.md frontmatter
---
title: QuickExpense Pro
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: true
license: mit
custom_domain: quickexpense.yourcompany.com
hardware: cpu-upgrade
models:
  - google/gemini-2.0-flash-exp
  - togethercomputer/llama-3.1-70b-instruct-turbo
---
```

---

## 📞 Support and Resources

### Documentation
- [Hugging Face Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Docker Spaces Guide](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [QuickBooks API Documentation](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account)

### Community
- [Hugging Face Discord](https://discord.gg/huggingface)
- [QuickExpense GitHub Issues](https://github.com/your-repo/quickexpense/issues)

### Getting Help
If you encounter issues:
1. Check the troubleshooting section above
2. Review Hugging Face Spaces logs
3. Test locally with Docker first
4. Open an issue in the project repository

---

## 📚 Related Documentation

- [Docker Usage Guide](./DOCKER_USAGE.md)
- [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)
- [Dependencies Guide](./DEPENDENCIES.md)
- [API Reference](./API_REFERENCE.md)
