# Security-hardened OPC UA Simulation Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
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

# Create certificates directory
RUN mkdir -p certs/trust

# Set ownership to non-root user
RUN chown -R opcua:opcua /app

# Switch to non-root user
USER opcua

# Expose OPC UA port
EXPOSE 4840

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('localhost', 4840)); s.close()" || exit 1

# Run the server
CMD ["python", "src/main.py"]
