# VectorBT Backtesting Microservice Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for TA-Lib (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY tests/ ./tests/

# Pre-compile Numba to reduce cold start time
RUN python -c "import vectorbt as vbt; import numba; print('VectorBT and Numba initialized')"

# Expose ports
EXPOSE 8080 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the service
ENTRYPOINT ["python", "main.py"]
CMD ["--port", "8080", "--mode", "http"]
