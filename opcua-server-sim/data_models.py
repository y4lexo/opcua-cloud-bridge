from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Quality(str, Enum):
    """Data quality enumeration for OPC UA values"""
    GOOD = "GOOD"
    BAD = "BAD"
    UNCERTAIN = "UNCERTAIN"


class TelemetryPoint(BaseModel):
    """Core data model for OPC UA telemetry data points"""
    timestamp: datetime = Field(..., description="UTC timestamp of the data point")
    enterprise: str = Field(..., description="Enterprise name (ISA-95 Level 4)")
    site: str = Field(..., description="Site name (ISA-95 Level 3)")
    area: str = Field(..., description="Area name (ISA-95 Level 2)")
    line: str = Field(..., description="Production line name (ISA-95 Level 2)")
    machine: str = Field(..., description="Machine/equipment name (ISA-95 Level 1)")
    tag: str = Field(..., description="OPC UA tag name")
    value: Any = Field(..., description="Tag value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    quality: Quality = Field(Quality.GOOD, description="Data quality status")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EnergyMonitoringConfig(BaseModel):
    """Configuration for energy monitoring use case"""
    power_tags: List[str] = Field(default_factory=list, description="Power consumption tags")
    energy_tags: List[str] = Field(default_factory=list, description="Energy consumption tags")
    voltage_tags: List[str] = Field(default_factory=list, description="Voltage measurement tags")
    current_tags: List[str] = Field(default_factory=list, description="Current measurement tags")
    aggregation_interval: int = Field(300, description="Aggregation interval in seconds")


class OEEConfig(BaseModel):
    """Configuration for Overall Equipment Effectiveness monitoring"""
    availability_tags: List[str] = Field(default_factory=list, description="Machine availability status tags")
    performance_tags: List[str] = Field(default_factory=list, description="Machine performance metrics tags")
    quality_tags: List[str] = Field(default_factory=list, description="Product quality metrics tags")
    cycle_count_tag: Optional[str] = Field(None, description="Cycle count tag name")
    production_rate_tag: Optional[str] = Field(None, description="Production rate tag name")


class PredictiveMaintenanceConfig(BaseModel):
    """Configuration for predictive maintenance use case"""
    vibration_tags: List[str] = Field(default_factory=list, description="Vibration sensor tags")
    temperature_tags: List[str] = Field(default_factory=list, description="Temperature sensor tags")
    pressure_tags: List[str] = Field(default_factory=list, description="Pressure sensor tags")
    maintenance_thresholds: Dict[str, float] = Field(default_factory=dict, description="Maintenance alert thresholds")
    prediction_horizon: int = Field(24, description="Prediction horizon in hours")


class AssetConfiguration(BaseModel):
    """Main configuration model for assets and their use cases"""
    asset_name: str = Field(..., description="Asset/equipment name")
    description: Optional[str] = Field(None, description="Asset description")
    opcua_endpoint: str = Field(..., description="OPC UA server endpoint URL")
    node_mapping: Dict[str, str] = Field(default_factory=dict, description="Mapping of logical names to OPC UA node IDs")
    
    # Use case configurations
    energy_monitoring: Optional[EnergyMonitoringConfig] = Field(None, description="Energy monitoring configuration")
    oee_monitoring: Optional[OEEConfig] = Field(None, description="OEE monitoring configuration")
    predictive_maintenance: Optional[PredictiveMaintenanceConfig] = Field(None, description="Predictive maintenance configuration")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional asset metadata")


class SiteConfiguration(BaseModel):
    """Configuration for a site containing multiple assets"""
    site_name: str = Field(..., description="Site name")
    enterprise: str = Field(..., description="Enterprise name")
    description: Optional[str] = Field(None, description="Site description")
    assets: List[AssetConfiguration] = Field(default_factory=list, description="List of assets in the site")
    
    # Site-level settings
    default_sampling_rate: int = Field(1000, description="Default sampling rate in milliseconds")
    buffer_size: int = Field(10000, description="Buffer size for data points")


class BridgeConfiguration(BaseModel):
    """Root configuration model for the OPC UA to Cloud Bridge"""
    enterprise_name: str = Field(..., description="Enterprise name")
    version: str = Field("1.0.0", description="Configuration version")
    sites: List[SiteConfiguration] = Field(default_factory=list, description="List of sites")
    
    # Global settings
    global_settings: Dict[str, Any] = Field(default_factory=dict, description="Global bridge settings")
    
    @classmethod
    def from_yaml(cls, yaml_content: str) -> "BridgeConfiguration":
        """Create configuration from YAML content"""
        import yaml
        data = yaml.safe_load(yaml_content)
        return cls(**data)
