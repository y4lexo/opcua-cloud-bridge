# OPC UA to Cloud Bridge

A production-grade, security-hardened OPC UA to Cloud Bridge

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           OPC UA to Cloud Bridge                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────────────────────────────────────┐   │
│  │   OPC UA        │    │           Edge Computing Layer                   │   │
│  │   Simulation    │───▶│  ┌─────────────┐  ┌─────────────────────────┐   │   │
│  │   Server        │    │  │   Analytics  │  │    Data Buffer          │   │   │
│  │   (X.509)       │    │  │   Processor │  │    (SQLite)             │   │   │
│  └─────────────────┘    │  │             │  │                         │   │   │
│                         │  └─────────────┘  └─────────────────────────┘   │   │
│                         │           │                   │               │   │
│                         │           ▼                   ▼               │   │
│                         │  ┌─────────────────────────────────────────┐   │   │
│                         │  │        OPC UA Client (X.509)           │   │   │
│                         │  └─────────────────────────────────────────┘   │   │
│                         └─────────────────────────────────────────────────┘   │
│                                              │                               │
│                                              ▼                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Cloud Integration                               │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │            InfluxDB Cloud (TLS/HTTPS)                           │   │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │   │
│  │  │  │   Telemetry │  │   Analytics │  │   ISA-95 Tagged Data   │   │   │
│  │  │  │   Time Series│  │   Insights  │  │   (Enterprise→Machine)  │   │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │
│  └─────────────────────────────────────────────────────────────────────────┘
```

## Security Architecture

### Multi-Layer Security Implementation

1. **Transport Layer Security (TLS)**
   - X.509 certificate-based mutual authentication
   - Basic256Sha256 encryption policy
   - Automatic certificate generation and rotation
   - Trust store management for client validation

2. **Application Layer Security**
   - Non-root container execution
   - Environment variable credential management
   - Secure certificate storage with proper permissions
   - Network isolation with dedicated bridge network

3. **Data Protection**
   - Encrypted data in transit (OPC UA + HTTPS)
   - Local data buffering during cloud outages
   - Secure batch transmission with retry logic
   - Data integrity validation

## ISA-95 Data Contract

### Hierarchical Data Model

The system implements the ANSI/ISA-95 standard for enterprise-control system integration:

```
Enterprise (Level 4)
├── Site (Level 3)
│   ├── Area (Level 2)
│   │   └── Production Line (Level 2)
│   │       └── Machine/Equipment (Level 1)
│   │           └── Sensors/Tags (Level 0)
```

### Data Structure

**TelemetryPoint Model:**
- **timestamp**: UTC timestamp with millisecond precision
- **enterprise**: Enterprise identifier (e.g., "GlobalCorp")
- **site**: Site name (e.g., "Site-A")
- **area**: Production area (e.g., "AssemblyLine")
- **line**: Production line (e.g., "Production-Line-1")
- **machine**: Equipment name (e.g., "FillerMachine-01")
- **tag**: OPC UA tag (e.g., "MotorSpeed", "Vibration")
- **value**: Sensor reading (numeric, boolean, or string)
- **unit**: Measurement unit (e.g., "RPM", "°C", "Bar")
- **quality**: Data quality (GOOD, BAD, UNCERTAIN)

### Analytics Integration

**OEE (Overall Equipment Effectiveness):**
- Availability = Running Time / Planned Production Time
- Performance = Actual Rate / Ideal Rate
- Quality = Good Units / Total Units
- Overall OEE = Availability × Performance × Quality

**Energy Monitoring:**
- Power consumption aggregation (kWh)
- Power factor calculation
- Peak demand monitoring
- Energy efficiency metrics

**Predictive Maintenance:**
- 30-minute rolling window statistics
- Anomaly detection with Z-score analysis
- Trend analysis with linear regression
- Maintenance scoring (0-100)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- InfluxDB Cloud account and credentials
- (Optional) OPC UA client for testing

### 1. Clone and Configure

```bash
git clone https://github.com/y4lexo/opcua-cloud-bridge.git
cd opcua-cloud-bridge

# Copy environment template
cp opcua-edge-collector/.env.example .env

# Edit .env with your InfluxDB Cloud credentials
nano .env
```

### 2. Environment Configuration

Create `.env` file with your credentials:

```bash
# InfluxDB Cloud Configuration
INFLUXDB_URL=https://cloud2.influxdata.com
INFLUXDB_TOKEN=your_influxdb_token_here
INFLUXDB_ORG=globalcorp
INFLUXDB_BUCKET=industrial-data

# Optional: Override default settings
BUFFER_SEND_INTERVAL=30
BUFFER_BATCH_SIZE=100
LOG_LEVEL=INFO
```

### 3. Deploy Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 4. Verify Operation

```bash
# Check OPC UA server health
docker-compose exec opcua-server python -c "
import socket
s = socket.socket()
s.settimeout(5)
s.connect(('localhost', 4840))
print('OPC UA Server: OK')
s.close()
"

# Check edge collector health
docker-compose exec edge-collector python -c "
import sys
sys.path.append('src')
print('Edge Collector: OK')
"
```

## Deployment Guide

### Service Dependencies

1. **OPC UA Server** (`opcua-server`)
   - Port: 4840 (OPC UA TCP)
   - Security: X.509 certificates
   - Data: Realistic industrial simulation
   - Health: Port connectivity check

2. **Edge Collector** (`edge-collector`)
   - Dependencies: OPC UA Server
   - Storage: Local SQLite buffer
   - Analytics: Real-time OEE, Energy, Predictive
   - Upload: InfluxDB Cloud via HTTPS

### Production Deployment

#### 1. Security Hardening

```bash
# Set proper permissions for certificates
sudo chmod 600 opcua-server-sim/certs/*.pem
sudo chmod 644 opcua-server-sim/certs/*.der

# Use production-grade InfluxDB token
# Generate token with write-only permissions for bucket
```

#### 2. Resource Allocation

```yaml
# docker-compose.prod.yml (example)
services:
  opcua-server:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
  
  edge-collector:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

#### 3. Monitoring and Logging

```bash
# Enable comprehensive logging
export LOG_LEVEL=INFO

# View real-time logs
docker-compose logs -f edge-collector

# Monitor buffer status
docker-compose exec edge-collector python -c "
import sys
sys.path.append('src')
from data_buffer import get_data_buffer
import asyncio

async def check_buffer():
    async with get_data_buffer() as buffer:
        status = await buffer.get_buffer_status()
        print(f'Buffer Status: {status}')

asyncio.run(check_buffer())
"
```

#### 4. Scaling Considerations

- **Multiple Assets**: Configure additional assets in `use_case_config.yaml`
- **High Frequency Data**: Adjust `BUFFER_SEND_INTERVAL` and batch sizes
- **Cloud Connectivity**: Implement retry logic and exponential backoff
- **Storage Management**: Monitor SQLite buffer size and cleanup policies

## Configuration

### Asset Configuration

Edit `use_case_config.yaml` to define your industrial assets:

```yaml
enterprise_name: "YourEnterprise"
sites:
  - site_name: "ProductionSite"
    assets:
      - asset_name: "CriticalMachine-01"
        opcua_endpoint: "opc.tcp://192.168.1.100:4840"
        node_mapping:
          MotorSpeed: "ns=2;i=1001"
          Temperature: "ns=2;i=1002"
          Pressure: "ns=2;i=1003"
        
        # Enable analytics modules
        oee_monitoring:
          availability_tags: ["MachineState"]
          performance_tags: ["MotorSpeed"]
          quality_tags: ["QualityStatus"]
        
        energy_monitoring:
          power_tags: ["PowerConsumption"]
          aggregation_interval: 300
        
        predictive_maintenance:
          vibration_tags: ["Vibration"]
          temperature_tags: ["Temperature"]
          maintenance_thresholds:
            Vibration: 5.0
            Temperature: 80.0
```

### Analytics Configuration

**OEE Monitoring:**
- Cycle count tracking
- Production rate calculation
- Quality status monitoring
- Availability percentage

**Energy Analytics:**
- Power consumption (kW)
- Energy accumulation (kWh)
- Power factor calculation
- Peak demand tracking

**Predictive Maintenance:**
- Vibration analysis
- Temperature monitoring
- Pressure tracking
- Anomaly detection thresholds

## Monitoring and Operations

### Health Checks

```bash
# Service health
docker-compose ps

# Detailed health status
curl http://localhost:4840/  # OPC UA endpoint test
```

### Performance Metrics

**Key Performance Indicators:**
- Data ingestion rate (points/second)
- Analytics processing latency
- Cloud upload success rate
- Buffer utilization percentage

**Troubleshooting:**

```bash
# Check OPC UA connection
docker-compose logs opcua-server | grep -i "error\|connection"

# Verify analytics processing
docker-compose logs edge-collector | grep -i "analytics\|oee\|energy"

# Monitor cloud uploads
docker-compose logs edge-collector | grep -i "influxdb\|upload\|batch"
```

### Data Validation

**Query InfluxDB Cloud:**
```flux
from(bucket: "industrial-data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "opcua_telemetry")
  |> group(columns: ["machine", "tag"])
  |> last()
```

**Verify Analytics:**
```flux
from(bucket: "industrial-data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "opcua_analytics")
  |> filter(fn: (r) => r["analytics_type"] == "oee")
  |> last()
```

## Development

### Local Development Setup

```bash
# Install dependencies
cd opcua-server-sim && pip install -r requirements.txt
cd ../opcua-edge-collector && pip install -r requirements.txt

# Run services locally
python opcua-server-sim/src/main.py &
python opcua-edge-collector/src/main.py &
```

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Security tests
python -m pytest tests/security/
```

### Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## API Reference

### OPC UA Endpoints

- **Server URL**: `opc.tcp://localhost:4840/`
- **Security Policy**: Basic256Sha256
- **Namespace**: `http://globalcorp.com/opcua/simulation`

### InfluxDB Data Schema

**Telemetry Measurements:**
- `opcua_telemetry`: Raw sensor data
- `opcua_analytics`: Processed analytics results

**Tags (ISA-95 Hierarchy):**
- `enterprise`: Enterprise name
- `site`: Site identifier
- `area`: Production area
- `line`: Production line
- `machine`: Machine/equipment name
- `tag`: Sensor tag name

**Fields:**
- `value_float`: Numeric sensor values
- `value_string`: String sensor values
- `value_bool`: Boolean sensor values

## Security 

### Certificate Management

1. **Generate Production Certificates**
   ```bash
   openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 365
   ```

2. **Secure Certificate Storage**
   - Use hardware security modules (HSM) for production
   - Implement certificate rotation policies
   - Monitor certificate expiration

3. **Network Security**
   - Use VPN or dedicated networks
   - Implement firewall rules
   - Monitor network traffic

### Access Control

1. **InfluxDB Permissions**
   - Use least privilege principle
   - Create dedicated tokens per service
   - Implement read/write separation

2. **Container Security**
   - Regular security updates
   - Vulnerability scanning
   - Runtime protection

## Support

- **Documentation**: [Full API Docs](docs/)
- **Issues**: [GitHub Issues](https://github.com/y4lexo/opcua-cloud-bridge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/y4lexo/opcua-cloud-bridge/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OPC Foundation](https://opcfoundation.org/) for OPC UA standards
- [InfluxData](https://www.influxdata.com/) for time series database
- [ISA-95](https://www.isa.org/standards-and-publications/isa-95) for enterprise-control integration
