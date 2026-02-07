# OPC UA Edge Collector

Intelligence and Resilience layers for the OPC UA to Cloud Bridge, providing real-time analytics and local data buffering capabilities.

## Features

### Intelligence Layer
- **OEE Analytics**: Real-time calculation of Availability, Performance, Quality, and Overall OEE
- **Energy Analytics**: Power factor calculation, consumption aggregation, and energy monitoring
- **Predictive Analytics**: Anomaly detection using rolling 30-minute window statistics and trend analysis

### Resilience Layer
- **Local Buffering**: SQLite-based local storage for telemetry and analytics data
- **Batch Operations**: Efficient save, retrieve, and delete operations for data batches
- **Cloud Outage Protection**: Ensures no data loss during network interruptions
- **Automatic Cleanup**: Configurable buffer size management and data retention policies

## Architecture

```
opcua-edge-collector/
├── src/
│   ├── analytics_processor.py    # Real-time analytics processing
│   ├── data_buffer.py           # Local SQLite buffer
│   └── __init__.py
├── requirements.txt              # Python dependencies
└── README.md                    # Documentation
```

## Analytics Processor

### OEE Analytics
Calculates Overall Equipment Effectiveness KPIs:
- **Availability**: Running time vs planned production time
- **Performance**: Actual vs ideal production rate
- **Quality**: Good units vs total units
- **Overall OEE**: Combined OEE score

### Energy Analytics
Monitors energy consumption and efficiency:
- **Power Consumption**: Real-time and aggregated consumption
- **Power Factor**: Calculated from voltage, current, and power data
- **Energy Accumulation**: Total energy consumption tracking
- **Peak/Min Power**: Consumption extremes monitoring

### Predictive Analytics
Detects anomalies and predicts maintenance needs:
- **Rolling Window Statistics**: 30-minute baseline calculation
- **Anomaly Detection**: Z-score based outlier detection
- **Trend Analysis**: Linear regression for trend calculation
- **Maintenance Scoring**: 0-100 predictive maintenance score
- **Threshold Monitoring**: Configurable maintenance thresholds

## Data Buffer

### Schema
- **telemetry table**: Raw OPC UA telemetry points
- **analytics table**: Processed analytics results
- **buffer_metadata table**: Buffer statistics and metadata

### Operations
- **save_point()**: Save individual telemetry points
- **save_batch()**: Save batch of telemetry and analytics data
- **get_batch()**: Retrieve unprocessed data batches
- **delete_batch()**: Remove processed batches
- **mark_processed()**: Mark batches as successfully processed

### Resilience Features
- **Automatic Size Management**: Configurable buffer size limits
- **Cleanup Policies**: Automatic deletion of old processed data
- **Batch Tracking**: Unique batch IDs for data integrity
- **Error Recovery**: Robust error handling and logging

## Usage

### Basic Analytics Processing
```python
from opcua_edge_collector import AnalyticsProcessor
from common.data_models import AssetConfiguration

# Load asset configuration
asset_config = AssetConfiguration.from_yaml(config_yaml)

# Initialize analytics processor
processor = AnalyticsProcessor(asset_config)

# Process telemetry point
telemetry_point = TelemetryPoint(...)
analytics_results = await processor.process_telemetry_point(telemetry_point)
```

### Data Buffering
```python
from opcua_edge_collector import get_data_buffer

# Initialize data buffer
async with get_data_buffer("edge_buffer.db", max_size_mb=100) as buffer:
    # Save telemetry data
    await buffer.save_telemetry_point(telemetry_point)
    
    # Save analytics results
    await buffer.save_analytics_result(analytics_data)
    
    # Get unprocessed batch
    batch = await buffer.get_telemetry_batch(batch_size=100)
    
    # Mark batch as processed
    await buffer.mark_batch_processed(batch_id)
```

### Combined Usage
```python
# Process telemetry and buffer results
async def process_and_buffer(telemetry_point, buffer, processor):
    # Process analytics
    analytics_results = await processor.process_telemetry_point(telemetry_point)
    
    # Buffer telemetry
    await buffer.save_telemetry_point(telemetry_point)
    
    # Buffer analytics if available
    if analytics_results['analytics']:
        await buffer.save_analytics_result(analytics_results)
```

## Configuration

Analytics modules are automatically initialized based on asset configuration:

```yaml
assets:
  - asset_name: "FillerMachine-01"
    oee_monitoring:
      availability_tags: ["MachineState"]
      performance_tags: ["MotorSpeed", "ProductionRate"]
      quality_tags: ["QualityStatus"]
      cycle_count_tag: "CycleCount"
    
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

## Performance Considerations

### Analytics Processing
- **Window Sizes**: Configurable rolling windows for different analytics
- **Baseline Calculation**: Automatic baseline after 15 minutes of data
- **Memory Management**: Deque-based windows with automatic size limits

### Buffer Performance
- **Batch Operations**: Efficient batch insert/retrieve operations
- **Indexing**: Optimized database indexes for fast queries
- **Connection Pooling**: Async SQLite connection management
- **Size Management**: Automatic cleanup when size limits exceeded

## Monitoring and Logging

Comprehensive logging for:
- Analytics processing status and errors
- Buffer operations and performance
- Data integrity and batch tracking
- Cleanup and maintenance operations

## Dependencies

- `asyncua==1.0.8` - OPC UA client/server library
- `aiosqlite==0.19.0` - Async SQLite database access
- `numpy==1.24.3` - Numerical computations for analytics
- `PyYAML==6.0.1` - Configuration parsing
- `pydantic==2.5.0` - Data validation and models

## Integration

The Edge Collector is designed to integrate with:
- **OPC UA Servers**: Connect to industrial OPC UA data sources
- **Cloud Gateways**: Upload buffered data when connectivity restored
- **Monitoring Systems**: Provide analytics insights and alerts
- **Historical Data**: Maintain local data during cloud outages
