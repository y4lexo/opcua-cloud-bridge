"""
OPC UA to Cloud Bridge - Common Package

This package provides core data models and utilities for the OPC UA to Cloud Bridge project.
"""

from .data_models import (
    TelemetryPoint,
    Quality,
    EnergyMonitoringConfig,
    OEEConfig,
    PredictiveMaintenanceConfig,
    AssetConfiguration,
    SiteConfiguration,
    BridgeConfiguration,
)

__version__ = "1.0.0"
__all__ = [
    "TelemetryPoint",
    "Quality",
    "EnergyMonitoringConfig",
    "OEEConfig",
    "PredictiveMaintenanceConfig",
    "AssetConfiguration",
    "SiteConfiguration",
    "BridgeConfiguration",
]
