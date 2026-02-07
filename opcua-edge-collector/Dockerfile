# OPC UA Edge Collector with Analytics and Cloud Integration
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r opcua && useradd -r -g opcua opcua

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY ../common/ ../common/
COPY ../use_case_config.yaml ../use_case_config.yaml

# Create directories for data and certificates
RUN mkdir -p data certs logs

# Set ownership to non-root user
RUN chown -R opcua:opcua /app

# Switch to non-root user
USER opcua

# Environment variables
ENV PYTHONPATH=/app
ENV INFLUXDB_URL=${INFLUXDB_URL:-https://cloud2.influxdata.com}
ENV INFLUXDB_ORG=${INFLUXDB_ORG:-globalcorp}
ENV INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-industrial-data}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.path.append('src'); from main import EdgeCollectorOrchestrator; print('Edge Collector healthy')" || exit 1

# Run the edge collector
CMD ["python", "src/main.py"]
