# Dependencies Guide for QuickExpense Docker

## 📦 Overview

This guide provides comprehensive information about all dependencies included in the QuickExpense Docker container, their purposes, versions, and how they work together to enable multi-agent receipt processing with Canadian tax compliance.

## 📋 Table of Contents

- [Core Dependencies](#core-dependencies)
- [Multi-Agent System](#multi-agent-system)
- [Image Processing](#image-processing)
- [API & Web Framework](#api--web-framework)
- [Data Processing](#data-processing)
- [System Dependencies](#system-dependencies)
- [Development Dependencies](#development-dependencies)
- [Version Management](#version-management)

---

## 🎯 Core Dependencies

### FastAPI Stack
```
fastapi==0.116.1              # Modern async web framework
uvicorn[standard]==0.35.0     # ASGI server with performance optimizations
python-multipart==0.0.20     # File upload support
pydantic==2.11.7              # Data validation and serialization
pydantic-settings==2.10.1    # Environment configuration management
```

**Purpose**: Core web application framework providing:
- High-performance async API endpoints
- Automatic OpenAPI/Swagger documentation
- Request/response validation
- File upload handling for receipt images
- Environment-based configuration

**Container Usage**:
```bash
# FastAPI runs on port 7860 in container
CMD ["uvicorn", "src.quickexpense.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

### HTTP Client
```
httpx==0.28.1                # Modern async HTTP client
```

**Purpose**:
- QuickBooks API communication
- External service integration
- Async HTTP requests for better performance

**Features**:
- HTTP/2 support
- Connection pooling
- Timeout handling
- SSL/TLS verification

---

## 🤖 Multi-Agent System

### AG2 (AutoGen) Framework
```
ag2[together]==0.9.9          # AG2 with TogetherAI integration
ag2[gemini]==0.9.9           # AG2 with Gemini integration
```

**Purpose**: Multi-agent conversation framework powering the 3-agent system:
- Agent orchestration and communication
- Conversation flow management
- Agent state persistence
- Built-in logging and monitoring

**Agent Types**:
1. **DataExtractionAgent**: Receipt image processing
2. **CRArulesAgent**: Canadian tax rule application
3. **TaxCalculatorAgent**: Tax calculation validation

### LLM Provider Integration
```
google-generativeai==0.8.5   # Gemini AI for image processing
together==1.5.26             # TogetherAI for text reasoning
google-auth==2.40.3          # Google authentication
google-api-python-client==2.181.0  # Google API client
```

**Purpose**: Hybrid LLM approach for cost optimization:
- **Gemini**: Vision tasks (receipt OCR, image understanding)
- **TogetherAI**: Text reasoning (tax rules, calculations)
- **Authentication**: Secure API access

### Supporting Libraries
```
aiohttp==3.12.15             # Async HTTP for agent communication
tenacity==9.1.2              # Retry mechanisms for API calls
diskcache==5.6.3             # Agent memory and caching
termcolor==3.1.0             # Colored console output for agents
```

**Purpose**:
- **aiohttp**: Async communication between agents
- **tenacity**: Robust retry logic for LLM API failures
- **diskcache**: Persistent agent memory and conversation history
- **termcolor**: Enhanced logging and debugging

---

## 🖼️ Image Processing

### Core Image Libraries
```
pillow==11.3.0               # Python Imaging Library
pillow-heif==1.1.0           # HEIC/HEIF support for iPhone photos
```

**Purpose**:
- Image format conversion and processing
- HEIC/HEIF support for iPhone photos taken with Camera app
- Image resizing and optimization
- Format validation and metadata extraction

**Supported Formats**:
- **Standard**: JPEG, PNG, GIF, BMP, WEBP
- **iPhone**: HEIC, HEIF (Live Photos, Portrait mode)
- **Documents**: Multi-page PDF processing

### PDF Processing
```
pymupdf==1.26.4              # PDF document processing
```

**Purpose**:
- Extract images from PDF receipts
- Multi-page PDF support
- Text extraction from PDF documents
- PDF metadata and structure analysis

**Container System Dependencies**:
```dockerfile
RUN apt-get install -y \
    libmupdf-dev \            # PDF processing library
    libjpeg-dev \             # JPEG image support
    libpng-dev \              # PNG image support
    libffi-dev                # FFI library for image processing
```

---

## 🌐 API & Web Framework

### Configuration Management
```
python-dotenv==1.1.1         # Environment variable loading
```

**Purpose**:
- Load environment variables from .env files
- Support for different environment configurations
- Secure credential management

**Container Configuration**:
```bash
# Environment variables loaded at startup
QB_CLIENT_ID=your_quickbooks_client_id
QB_CLIENT_SECRET=your_quickbooks_client_secret
GEMINI_API_KEY=your_gemini_api_key
TOGETHER_API_KEY=your_together_api_key
```

### Utilities
```
click==8.2.1                 # Command-line interface framework
rich==14.1.0                 # Rich text and beautiful formatting
typer==0.15.3                # Modern CLI framework built on Click
```

**Purpose**:
- CLI interface for receipt processing
- Beautiful console output and progress bars
- Command-line argument parsing
- Error handling and user feedback

---

## 📊 Data Processing

### Data Analysis
```
pandas==2.3.3               # Data manipulation and analysis
numpy==2.3.3                # Numerical computing
```

**Purpose**:
- Business rules CSV processing
- Tax calculation and analysis
- Data validation and cleaning
- Statistical analysis of processing results

**Business Rules Integration**:
```python
# Load CRA compliance rules from CSV
import pandas as pd
rules_df = pd.read_csv('/home/user/app/config/cra_rules.csv')
```

### Date/Time Processing
```
python-dateutil==2.9.0.post0  # Flexible date parsing
pytz==2025.2                   # Timezone handling
```

**Purpose**:
- Parse receipt dates in various formats
- Handle timezone conversions
- Support for Canadian tax year calculations
- Date validation and normalization

---

## 🖥️ System Dependencies

### Container Base Image
```dockerfile
FROM python:3.12-slim
```

**Included in Base**:
- Python 3.12 runtime
- pip package manager
- Essential system libraries
- UTF-8 locale support

### System Packages
```dockerfile
RUN apt-get update && apt-get install -y \
    curl \                    # Health checks and API testing
    libmupdf-dev \           # PDF processing library
    libjpeg-dev \            # JPEG image support
    libpng-dev \             # PNG image support
    libffi-dev               # Foreign Function Interface
```

**Purpose**:
- **curl**: Health check endpoint monitoring
- **libmupdf-dev**: PDF document processing support
- **libjpeg-dev**: JPEG image processing
- **libpng-dev**: PNG image support
- **libffi-dev**: Required for image processing libraries

### Container User Setup
```dockerfile
# Create non-root user (HF Spaces requirement)
RUN useradd -m -u 1000 user
USER user
```

**Security Features**:
- Non-root execution for security
- UID 1000 for Hugging Face Spaces compatibility
- Proper file permissions
- Restricted system access

---

## 🛠️ Development Dependencies

### Code Quality (Not in Production Container)
```
# These are excluded from production requirements.txt
pytest>=8.0.0               # Testing framework
pytest-asyncio>=0.23.0      # Async testing support
pytest-cov>=5.0.0           # Coverage reporting
ruff>=0.6.0                 # Fast Python linter
black>=25.1.0               # Code formatter
mypy>=1.17.1                # Static type checking
```

**Purpose**: Development-time code quality and testing (not included in Docker image)

---

## 📌 Version Management

### Requirements Generation
The production `requirements.txt` is generated from `pyproject.toml`:

```bash
# Generate pinned requirements
uv pip compile pyproject.toml --output-file requirements.txt --resolution highest
```

### Version Pinning Strategy
- **Exact versions** for critical dependencies (AG2, FastAPI)
- **Compatible versions** for stable libraries (Pillow, pandas)
- **Security updates** applied regularly

### Container Build Optimization
```dockerfile
# Copy requirements first for Docker layer caching
COPY --chown=user:user requirements.txt .

# Install with optimizations
RUN pip install --no-cache-dir --no-compile -r requirements.txt && \
    find /usr/local -name "__pycache__" -exec rm -rf {} + && \
    find /usr/local -name "*.pyc" -delete
```

**Optimizations**:
- `--no-cache-dir`: Reduces image size
- `--no-compile`: Skips bytecode compilation
- Cache cleanup: Removes Python cache files
- Layer separation: Better Docker build caching

---

## 🔍 Dependency Analysis

### Image Size Breakdown
```
Base python:3.12-slim:    ~150MB
System dependencies:       ~50MB
Python packages:          ~800MB
Application code:          ~10MB
Total optimized image:    ~1.01GB
```

### Critical Path Dependencies
```
Receipt Processing Flow:
├── pillow/pillow-heif     → Image format support
├── pymupdf                → PDF processing
├── google-generativeai    → Gemini AI vision
├── ag2[together]          → Agent orchestration
└── fastapi/uvicorn        → API serving
```

### Network Dependencies
The container requires outbound HTTPS access to:
- `generativelanguage.googleapis.com` (Gemini AI)
- `api.together.xyz` (TogetherAI)
- `sandbox-quickbooks.api.intuit.com` (QuickBooks)

---

## 🔧 Troubleshooting Dependencies

### Common Issues

#### 1. Image Processing Failures
```bash
# Check pillow-heif installation
docker exec container python -c "import pillow_heif; print('HEIC support OK')"

# Check system dependencies
docker exec container dpkg -l | grep -E "(libjpeg|libpng|libmupdf)"
```

#### 2. AG2 Import Errors
```bash
# Verify AG2 installation
docker exec container python -c "import autogen; print(autogen.__version__)"

# Check provider integrations
docker exec container python -c "from autogen.oai import create; print('AG2 OK')"
```

#### 3. PDF Processing Issues
```bash
# Test PyMuPDF
docker exec container python -c "import fitz; print('PDF support OK')"

# Check system library
docker exec container ls -la /usr/lib/*/libmupdf*
```

### Dependency Conflicts
```bash
# Check for version conflicts
docker exec container pip check

# List installed packages
docker exec container pip list > installed_packages.txt
```

### Performance Monitoring
```bash
# Monitor memory usage during processing
docker stats container_name

# Check package load times
docker exec container python -c "
import time
start = time.time()
import pandas, numpy, PIL, autogen
print(f'Package load time: {time.time() - start:.2f}s')
"
```

---

## 🚀 Optimization Recommendations

### Memory Optimization
- Use streaming for large file processing
- Implement image resizing before processing
- Clear agent memory after processing

### Performance Tuning
- Enable HTTP/2 for external API calls
- Use connection pooling for database access
- Implement caching for business rules

### Security Considerations
- Regular dependency updates
- Vulnerability scanning
- Minimal system permissions

---

## 📚 Related Documentation

- [Docker Usage Guide](./DOCKER_USAGE.md)
- [Multi-Agent Architecture](./MULTI_AGENT_ARCHITECTURE.md)
- [Hugging Face Deployment](./HUGGING_FACE_DEPLOYMENT.md)
- [API Reference](./API_REFERENCE.md)
