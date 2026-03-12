# Use Python base image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies and curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
# COPY requirements.txt* ./

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir setfit "transformers<5.0.0" "scikit-learn>=1.8.0" fastapi uvicorn[standard] gdown optimum gunicorn

# Copy application files
COPY main.py ./

# Download model from Google Drive and verify extraction
RUN gdown "https://drive.google.com/uc?id=127S5LIzjnoWlnYCX_6nLvb2pS2Yy0bEA" -O model.zip && \
    unzip -q model.zip && \
    rm model.zip && \
    test -d poison_detection_model || (echo "ERROR: poison_detection_model not found after extraction" && exit 1)

# Create non-root user for security
RUN useradd -m -u 10001 modeluser && \
    chown -R modeluser:modeluser /app

# Switch to non-root user
USER 10001

# Expose port (documentation only, not published)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI server with production settings
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
