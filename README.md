# OPC UA to Cloud Bridge - Energy Platform

A production-grade, security-hardened OPC UA to Cloud Bridge transformed for energy management and renewable energy monitoring.

## Energy-Focused Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     OPC UA to Cloud Bridge - Energy Platform                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────────────────────────────────────┐   │
│  │   OPC UA        │    │           Edge Computing Layer                   │   │
│  │   Energy        │───▶│  ┌─────────────┐  ┌─────────────────────────┐   │   │
│  │   Simulation    │    │  │   Energy     │  │    Data Buffer          │   │   │
│  │   Server        │    │  │   Analytics  │  │    (SQLite)             │   │   │
│  │   (X.509)       │    │  │   Processor │  │                         │   │   │
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
│  │  │  │   Energy    │  │   Energy    │  │   ISA-95 Tagged Data   │   │   │
│  │  │  │   Telemetry │  │   KPIs      │  │   (Enterprise→Site)     │   │   │
│  │  │  │   Time Series│  │   Insights  │  │   └─Equipment          │   │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │
│  └─────────────────────────────────────────────────────────────────────────┘
```

## Energy Equipment Support

### Supported Energy Assets
- **Solar Inverters**: 500kW MPPT tracking with grid integration
- **Battery Storage**: 1MWh lithium-ion systems with SoC monitoring
- **Smart Meters**: Grid interface monitoring with import/export tracking
- **Load Panels**: Commercial load distribution and consumption monitoring
- **BEMS Sensors**: Building energy management system integration

### Energy Data Points
- **Power Metrics**: Active/reactive power, import/export, demand
- **Energy Metrics**: Cumulative kWh, charge/discharge energy
- **Quality Metrics**: Power factor, THD, frequency stability
- **Efficiency Metrics**: Inverter efficiency, battery round-trip efficiency
- **Renewable Metrics**: Irradiance, renewable share, energy independence

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

## ISA-95 Energy Data Contract

### Energy-Focused Hierarchical Data Model

The system implements the ANSI/ISA-95 standard adapted for energy infrastructure:

```
Enterprise (Level 4) - GlobalEnergy
├── Site (Level 3)
│   ├── SolarFarm-A (Generation)
│   ├── BatteryStorage-A (Storage)
│   └── CommercialSite-A (Consumption)
│       └── Equipment (Level 1)
│           ├── Solar_Inverter_01
│           ├── Battery_Storage_01
│           ├── Smart_Meter_Grid
│           └── Load_Panel_A
│               └── Variables (Level 0)
│                   ├── Voltage_L1/L2/L3
│                   ├── Current_L1/L2/L3
│                   ├── Power_Active/Reactive
│                   ├── Energy_Total
│                   ├── SoC
│                   └── Efficiency
```

### Energy TelemetryPoint Model

- **timestamp**: UTC timestamp with millisecond precision
- **enterprise**: Enterprise identifier (e.g., "GlobalEnergy")
- **site**: Site name (e.g., "SolarFarm-A")
- **area**: Functional area (e.g., "Generation", "Storage", "Grid-Interface")
- **line**: Equipment line (e.g., "Solar-Array-1", "Battery-Bank-1")
- **machine**: Equipment name (e.g., "Solar_Inverter_01", "Battery_Storage_01")
- **tag**: Energy tag (e.g., "Power_Active", "SoC", "Irradiance")
- **value**: Sensor reading (numeric, boolean, or string)
- **unit**: Measurement unit (e.g., "kW", "kWh", "%", "V")
- **quality**: Data quality (GOOD, BAD, UNCERTAIN)

### Energy Analytics Integration

**Energy KPIs:**
- Total power generation and consumption (kW)
- Cumulative energy tracking (kWh)
- Power factor and grid quality metrics
- Battery efficiency and round-trip efficiency
- Renewable share and energy independence percentage
- Load factor and demand management metrics

**Predictive Maintenance:**
- Battery SoC anomaly detection (rapid drops)
- Power spike detection and demand anomalies
- Inverter efficiency degradation monitoring
- Voltage deviation and grid stability analysis
- Temperature monitoring for thermal management

**Energy Anomaly Detection:**
- 20% SoC drop in 5 minutes (battery issues)
- 2x power spike in 1 minute (load faults)
- 15% efficiency drop in 10 minutes (equipment degradation)
- 10% voltage deviation in 2 minutes (grid instability)

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
INFLUXDB_ORG=globalenergy
INFLUXDB_BUCKET=energy-data

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

Edit `use_case_config.yaml` to define your energy assets:

```yaml
enterprise_name: "GlobalEnergy"
sites:
  - site_name: "SolarFarm-A"
    enterprise: "GlobalEnergy"
    description: "Main solar energy generation facility with battery storage"
    assets:
      - asset_name: "Solar_Inverter_01"
        description: "500kW solar inverter with MPPT tracking and grid integration"
        opcua_endpoint: "opc.tcp://192.168.1.100:4840"
        node_mapping:
          Voltage_L1: "ns=2;i=1001"
          Voltage_L2: "ns=2;i=1002"
          Voltage_L3: "ns=2;i=1003"
          Current_L1: "ns=2;i=1004"
          Current_L2: "ns=2;i=1005"
          Current_L3: "ns=2;i=1006"
          Power_Active: "ns=2;i=1007"
          Power_Reactive: "ns=2;i=1008"
          Energy_Total: "ns=2;i=1009"
          Frequency: "ns=2;i=1010"
          Temperature: "ns=2;i=1011"
          Inverter_State: "ns=2;i=1012"
          Irradiance: "ns=2;i=1013"
          Efficiency: "ns=2;i=1014"
        
        # Energy Monitoring Configuration
        energy_monitoring:
          power_tags: ["Power_Active"]
          energy_tags: ["Energy_Total"]
          voltage_tags: ["Voltage_L1", "Voltage_L2", "Voltage_L3"]
          current_tags: ["Current_L1", "Current_L2", "Current_L3"]
          aggregation_interval: 300
        
        # Energy Analytics Configuration
        energy_analytics:
          efficiency_tags: ["Efficiency"]
          renewable_tags: ["Irradiance"]
          battery_tags: []
          load_tags: []
          aggregation_interval: 300
        
        # Predictive Maintenance Configuration
        predictive_maintenance:
          temperature_tags: ["Temperature"]
          maintenance_thresholds:
            Temperature: 85.0
          prediction_horizon: 24
```

### Energy Analytics Configuration

**Energy KPI Monitoring:**
- Power generation and consumption tracking
- Energy accumulation and net metering
- Power factor and grid quality analysis
- Battery efficiency and SoC monitoring
- Renewable share and energy independence

**Predictive Maintenance:**
- Temperature monitoring for thermal management
- Efficiency degradation detection
- Voltage and current anomaly detection
- Battery health monitoring
- Grid stability analysis

**Energy Anomaly Detection:**
- Battery SoC rapid drop detection
- Power spike and demand anomaly detection
- Inverter efficiency monitoring
- Voltage deviation analysis
- Grid frequency stability

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
- Energy analytics processing latency
- Cloud upload success rate
- Buffer utilization percentage
- Energy KPI calculation accuracy

**Troubleshooting:**

```bash
# Check OPC UA connection
docker-compose logs opcua-server | grep -i "error\|connection"

# Verify energy analytics processing
docker-compose logs edge-collector | grep -i "analytics\|energy\|kpi"

# Monitor cloud uploads
docker-compose logs edge-collector | grep -i "influxdb\|upload\|batch"
```

### Data Validation

**Query InfluxDB Cloud:**
```flux
from(bucket: "energy-data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "opcua_telemetry")
  |> group(columns: ["machine", "tag"])
  |> last()
```

**Verify Energy Analytics:**
```flux
from(bucket: "energy-data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "opcua_analytics")
  |> filter(fn: (r) => r["analytics_type"] == "energy_kpis")
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
- **Namespace**: `http://globalenergy.com/opcua/simulation`

### InfluxDB Energy Data Schema

**Telemetry Measurements:**
- `opcua_telemetry`: Raw energy sensor data
- `opcua_analytics`: Processed energy analytics results

**Tags (ISA-95 Energy Hierarchy):**
- `enterprise`: Enterprise name
- `site`: Site identifier
- `area`: Functional area (Generation, Storage, Grid-Interface)
- `line`: Equipment line
- `machine`: Energy equipment name
- `tag`: Energy sensor tag name

**Fields:**
- `value_float`: Numeric sensor values
- `value_string`: String sensor values
- `value_bool`: Boolean sensor values

## Legacy Compatibility

This energy platform maintains backward compatibility with industrial equipment:

**Optional OEE Support:**
- Legacy OEE analytics available for mixed deployments
- Industrial equipment tags still supported
- Gradual migration path from industrial to energy focus

**LabVIEW/PLC Compatibility:**
- Existing industrial protocols supported
- Mixed energy and industrial asset configurations
- Flexible node mapping for diverse equipment types

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
- Energy industry partners for renewable energy domain expertise
