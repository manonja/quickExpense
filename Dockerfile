# =============================================================================
# QuickExpense Docker Image for Hugging Face Spaces
# =============================================================================
# This Dockerfile creates a production-ready container for the QuickExpense
# multi-agent receipt processing system with QuickBooks integration.
#
# Key Features:
# - Multi-agent AI system (Gemini + TogetherAI)
# - FastAPI backend on port 7860
# - Persistent token storage support
# - Non-root user (HF Spaces requirement)
# - Health checks and proper logging
# - Support for HEIC, PDF, and image processing
# - Optimized for size and performance
# =============================================================================

# -----------------------------------------------------------------------------
# Base Image
# -----------------------------------------------------------------------------
FROM python:3.12-slim

# -----------------------------------------------------------------------------
# System Dependencies (Combined with cleanup)
# -----------------------------------------------------------------------------
# Install system packages needed for image processing, PDF handling, and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmupdf-dev \
    libjpeg-dev \
    libpng-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# -----------------------------------------------------------------------------
# Create Non-Root User (Hugging Face Requirement)
# -----------------------------------------------------------------------------
RUN useradd -m -u 1000 user

# -----------------------------------------------------------------------------
# Environment Setup
# -----------------------------------------------------------------------------
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH=/home/user/app/src:$PYTHONPATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    # Default environment settings for production
    DEBUG=false \
    LOG_LEVEL=INFO \
    # AG2 logging configuration
    ENABLE_AG2_LOGGING=true \
    ENABLE_RUNTIME_LOGGING=true \
    ENABLE_CONVERSATION_LOGGING=true \
    # QuickBooks default settings
    QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com \
    QB_REDIRECT_URI=https://USER_SPACE_NAME.hf.space/api/web/callback \
    QB_OAUTH_ENVIRONMENT=sandbox \
    # LLM provider configuration
    LLM_PROVIDER=together \
    LLM_FALLBACK_ENABLED=true \
    # Gemini configuration
    GEMINI_MODEL=gemini-2.0-flash-exp \
    GEMINI_TIMEOUT=30 \
    # TogetherAI configuration
    TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo \
    TOGETHER_MAX_TOKENS=4096 \
    TOGETHER_TEMPERATURE=0.2

# -----------------------------------------------------------------------------
# Set Working Directory
# -----------------------------------------------------------------------------
WORKDIR $HOME/app

# -----------------------------------------------------------------------------
# Install Python Dependencies
# -----------------------------------------------------------------------------
# Copy requirements first for better Docker layer caching
COPY --chown=user:user requirements.txt .

# Install dependencies with optimizations for smaller image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-compile -r requirements.txt && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name "*.pyc" -delete

# -----------------------------------------------------------------------------
# Copy Application Code
# -----------------------------------------------------------------------------
# Copy source code
COPY --chown=user:user src/ $HOME/app/src/

# Copy configuration files (business rules, etc.)
COPY --chown=user:user config/ $HOME/app/config/

# Create application directories
RUN mkdir -p $HOME/app/data && \
    mkdir -p $HOME/app/logs && \
    chown -R user:user $HOME/app

# -----------------------------------------------------------------------------
# Create Persistent Storage Directory
# -----------------------------------------------------------------------------
# HF Spaces mounts persistent storage at /data
RUN mkdir -p /data && chown -R user:user /data

# Create symlink from app data directory to persistent storage
RUN ln -sf /data $HOME/app/data/persistent

# -----------------------------------------------------------------------------
# Switch to Non-Root User
# -----------------------------------------------------------------------------
USER user

# -----------------------------------------------------------------------------
# Expose Port
# -----------------------------------------------------------------------------
EXPOSE 7860

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# -----------------------------------------------------------------------------
# Startup Command
# -----------------------------------------------------------------------------
CMD ["uvicorn", "src.quickexpense.main:app", "--host", "0.0.0.0", "--port", "7860"]
