# OPC UA Simulation Server

Security-hardened OPC UA server with X.509 certificate authentication and realistic data simulation.

## Features

- **Security**: X.509 certificate-based authentication with Basic256Sha256 security policy
- **Dynamic Node Creation**: Automatically creates OPC UA nodes from `use_case_config.yaml`
- **Realistic Simulation**: Generates realistic industrial data with proper variations and patterns
- **ISA-95 Compliant**: Full hierarchy support for enterprise, site, area, line, and machine levels
- **Docker Support**: Containerized deployment with security best practices

## Architecture

```
opcua-server-sim/
├── src/
│   ├── main.py              
│   ├── cert_utils.py        
│   └── __init__.py
├── certs/                  
├── requirements.txt        
├── Dockerfile              
└── README.md
```

## Security Implementation

### Certificate Management
- Self-signed X.509 certificates with 2048-bit RSA keys
- Automatic certificate generation in `certs/` directory
- Trust store for client certificate validation
- Certificate includes DNS names and IP addresses for proper validation

### Security Policies
- Basic256Sha256_SignAndEncrypt
- Basic256Sha256_Sign
- X.509 user authentication
- Username/password authentication (fallback)

### Docker Security
- Non-root user execution
- Minimal base image (python:3.11-slim)
- Health checks for monitoring
- Proper file permissions

## Data Simulation

The server simulates realistic industrial data for:

- **Motor Speed**: 1800 RPM with variations (±50 RPM)
- **Vibration**: 2.0 mm/s baseline with occasional spikes (8-12 mm/s)
- **Temperature**: 45°C with daily cycle variations
- **Pressure**: 6.0 Bar with normal fluctuations
- **Cycle Count**: Incrementing counters (1-3 per cycle)
- **Machine State**: Running/Idle/Starting/Stopping/Maintenance
- **Production Rate**: 200 units/hour with efficiency variations
- **Power Consumption**: 15 kW with load factor variations
- **Quality Status**: Good/Warning/Error with weighted probabilities

## Configuration

The server reads from `../use_case_config.yaml` to dynamically create nodes based on the ISA-95 hierarchy and asset configurations.

## Usage

### Local Development
```bash
cd opcua-server-sim
pip install -r requirements.txt
python src/main.py
```

### Docker Deployment
```bash
cd opcua-server-sim
docker build -t opcua-simulation-server .
docker run -p 4840:4840 opcua-simulation-server
```

### Docker Compose
```yaml
version: '3.8'
services:
  opcua-server:
    build: ./opcua-server-sim
    ports:
      - "4840:4840"
    volumes:
      - ./certs:/app/certs
    restart: unless-stopped
```

## OPC UA Endpoint

- **URL**: `opc.tcp://0.0.0.0:4840/`
- **Security**: Basic256Sha256 with X.509 certificates
- **Namespace**: `http://globalcorp.com/opcua/simulation`

## Monitoring

The server includes comprehensive logging:
- Certificate generation and security setup
- Dynamic node creation
- Simulation loop status
- Error handling and recovery

Health checks are available at the container level for monitoring the server availability.

## Dependencies

- `asyncua==1.0.8` - OPC UA client/server library
- `cryptography==41.0.7` - Certificate generation
- `PyYAML==6.0.1` - Configuration parsing
