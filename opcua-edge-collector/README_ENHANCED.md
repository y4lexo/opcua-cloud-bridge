# OPC UA Edge Collector - Enhanced for Real-World PLC Connections

This enhanced version of the OPC UA Edge Collector is specifically designed for connecting to physical PLCs and industrial OPC UA servers in real-world network environments.

## 🚀 New Features

### 1. Environment Variable Configuration Override
Override configuration without modifying YAML files:

```bash
# Override OPC UA server URL for all assets
export OPCUA_SERVER_URL="opc.tcp://192.168.1.100:4840/"

# Override specific Node IDs
export NODE_ID_PLC1_Temperature="ns=2;i=1001"
export NODE_ID_PLC1_Pressure="ns=2;i=1002"
export NODE_ID_PLC2_MotorSpeed="ns=3;s=Motor_Speed"

# Override security policy
export OPCUA_SECURITY_POLICY="None"  # For older PLCs
export OPCUA_SECURITY_POLICY="Basic256Sha256"  # For secure connections

# Override connection settings
export OPCUA_CONNECTION_TIMEOUT="15.0"
```

### 2. Exponential Backoff Reconnection
- **Automatic retry** with increasing delays (1s, 2s, 4s, 8s, 16s...)
- **Jitter addition** to prevent thundering herd problems
- **Connection health monitoring** with automatic reconnection
- **Configurable retry limits** and maximum delays

### 3. Dynamic Security Policy Negotiation
- **Automatic discovery** of server security capabilities
- **Graceful fallback** to lower security if needed
- **Environment variable override** for specific security policies
- **Support for legacy PLCs** with no security

### 4. Node Discovery Utility
Discover and explore OPC UA address spaces:

```bash
# Basic discovery
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/

# With security
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --security-policy Basic256Sha256

# Deep discovery
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --max-depth 5

# Monitor specific node
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --monitor-node "ns=2;i=1001"
```

## 📋 Usage Examples

### Basic Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables for your PLC
export OPCUA_SERVER_URL="opc.tcp://your-plc-ip:4840/"
export OPCUA_SECURITY_POLICY="None"  # If PLC has no security

# Run the collector
python src/main.py
```

### Advanced Configuration
```bash
# Multiple PLCs with different settings
export NODE_ID_PLC1_Temperature="ns=2;i=1001"
export NODE_ID_PLC1_Pressure="ns=2;i=1002"
export NODE_ID_PLC2_Speed="ns=3;s=Motor_Speed"

# Connection tuning
export OPCUA_CONNECTION_TIMEOUT="20.0"
export OPCUA_RETRY_ATTEMPTS="10"

# Run with verbose logging
python src/main.py --verbose
```

### Node Discovery Workflow
```bash
# 1. Discover what's available on the PLC
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --verbose

# 2. Find the specific Node IDs you need
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --max-depth 4

# 3. Monitor a specific node to verify it's working
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --monitor-node "ns=2;i=1001"

# 4. Set environment variables and run collector
export NODE_ID_PLC1_Temperature="ns=2;i=1001"
python src/main.py
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPCUA_SERVER_URL` | Override OPC UA endpoint for all assets | `opc.tcp://192.168.1.100:4840/` |
| `OPCUA_SECURITY_POLICY` | Override security policy | `None`, `Basic256Sha256` |
| `OPCUA_CONNECTION_TIMEOUT` | Connection timeout in seconds | `15.0` |
| `OPCUA_RETRY_ATTEMPTS` | Maximum retry attempts | `10` |
| `OPCUA_RETRY_DELAY` | Base retry delay in seconds | `2.0` |
| `NODE_ID_<ASSET>_<TAG>` | Override specific Node ID | `NODE_ID_PLC1_Temp=ns=2;i=1001` |

### Security Policy Options

- **None** - No security (for legacy PLCs)
- **Basic128Rsa15** - Basic security
- **Basic256Sha256** - Recommended security
- **Auto** - Automatic negotiation (default)

## 🌐 Network Considerations

### Industrial Network Challenges
- **Intermittent connectivity** - Handled by exponential backoff
- **High latency** - Configurable timeouts and retry strategies
- **Legacy equipment** - Dynamic security policy fallback
- **Network segmentation** - Environment-based configuration

### Best Practices
1. **Start with no security** for discovery, then enable security
2. **Use longer timeouts** for unreliable networks
3. **Monitor connection health** with built-in health checks
4. **Test with node discovery** before configuring production

## 📊 Monitoring and Debugging

### Logging Levels
```bash
# Standard logging
python src/main.py

# Verbose logging for debugging
python src/main.py --verbose

# Debug level for troubleshooting
python src/main.py --debug
```

### Health Monitoring
The collector includes built-in health monitoring:
- Connection status for each asset
- Buffer utilization
- Cloud sender statistics
- Analytics processor health

### Common Issues and Solutions

#### Connection Failures
```bash
# Try with no security first
export OPCUA_SECURITY_POLICY="None"

# Increase timeout
export OPCUA_CONNECTION_TIMEOUT="30.0"

# Check network connectivity
ping 192.168.1.100
```

#### Node ID Issues
```bash
# Discover available nodes
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/

# Test specific node
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/ --monitor-node "ns=2;i=1001"
```

#### Security Policy Issues
```bash
# Discover supported policies
python src/discover_nodes.py opc.tcp://192.168.1.100:4840/

# Try different policies
export OPCUA_SECURITY_POLICY="Basic128Rsa15"
export OPCUA_SECURITY_POLICY="Basic256Sha256"
```

## 🔄 Migration from Simulation

To migrate from the Docker-based simulation to real PLCs:

1. **Update environment variables** with your PLC endpoints
2. **Run node discovery** to find correct Node IDs
3. **Configure security policies** based on PLC capabilities
4. **Test connections** with the discovery utility
5. **Deploy with monitoring** enabled

## 📝 Example Configuration

```yaml
# use_case_config.yaml (base configuration)
enterprise_name: "Manufacturing Corp"
version: "1.0.0"
sites:
  - site_name: "Production Floor"
    enterprise: "Manufacturing Corp"
    assets:
      - asset_name: "PLC1"
        opcua_endpoint: "opc.tcp://localhost:4840/"  # Will be overridden by env var
        node_mapping:
          Temperature: "ns=2;i=1001"  # Will be overridden by NODE_ID_PLC1_Temperature
          Pressure: "ns=2;i=1002"
        security_settings:
          security_policy: "Basic256Sha256"  # Will be overridden by OPCUA_SECURITY_POLICY
        metadata:
          site: "Production Floor"
          area: "Line 1"
          line: "Assembly"
```

```bash
# Environment overrides for production
export OPCUA_SERVER_URL="opc.tcp://192.168.1.100:4840/"
export OPCUA_SECURITY_POLICY="None"
export NODE_ID_PLC1_Temperature="ns=2;i=3001"
export NODE_ID_PLC1_Pressure="ns=2;i=3002"
export OPCUA_CONNECTION_TIMEOUT="20.0"

python src/main.py
```

## 🛠️ Development and Testing

### Local Testing
```bash
# Test with simulation server
export OPCUA_SERVER_URL="opc.tcp://localhost:4840/"
python src/main.py

# Test discovery utility
python src/discover_nodes.py opc.tcp://localhost:4840/
```

### Integration Testing
```bash
# Test with various security policies
for policy in None Basic128Rsa15 Basic256Sha256; do
    export OPCUA_SECURITY_POLICY=$policy
    echo "Testing with policy: $policy"
    python src/discover_nodes.py $ENDPOINT
done
```

## 📚 Additional Resources

- [OPC UA Specification](https://reference.opcfoundation.org/v104/)
- [asyncua Documentation](https://asyncua.readthedocs.io/)
- [Industrial Network Security Best Practices](https://www.iec.ch/)

## 🆘 Troubleshooting

For issues specific to real-world PLC connections:

1. **Check network connectivity** first
2. **Use node discovery** to verify server capabilities
3. **Start with no security** and enable gradually
4. **Monitor logs** for connection patterns
5. **Adjust timeouts** for network conditions

The enhanced edge collector is designed to be robust and adaptable to various industrial environments while maintaining the same analytics and cloud integration capabilities as the original simulation version.
