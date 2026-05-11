# Use Python base image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir setfit "transformers<5.0.0" "scikit-learn>=1.8.0" fastapi uvicorn[standard] optimum gunicorn huggingface_hub

# Copy application files
COPY main.py ./
COPY app ./app

# Create non-root user for security
RUN useradd -m -u 10001 modeluser && \
    chown -R modeluser:modeluser /app

# Switch to non-root user
USER 10001

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI server
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]