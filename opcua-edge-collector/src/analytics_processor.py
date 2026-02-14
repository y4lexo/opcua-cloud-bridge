"""Real-time analytics processor for OPC UA Edge Gateway"""

import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import deque, defaultdict
import numpy as np

# Add parent directory to path for common models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import (
    TelemetryPoint, 
    Quality, 
    EnergyMonitoringConfig, 
    EnergyAnalyticsConfig,
    OEEConfig, 
    PredictiveMaintenanceConfig,
    AssetConfiguration
)

logger = logging.getLogger(__name__)


class OEEAnalytics:
    """Overall Equipment Effectiveness analytics processor (Legacy/Optional)"""
    
    def __init__(self, config: OEEConfig):
        self.config = config
        self.availability_window = deque(maxlen=3600)  # 1 hour window
        self.performance_window = deque(maxlen=3600)   # 1 hour window
        self.quality_window = deque(maxlen=3600)       # 1 hour window
        self.cycle_count_history = deque(maxlen=100)    # Recent cycle counts
        self.planned_production_time = 3600  # 1 hour in seconds
        
    def process_telemetry(self, point: TelemetryPoint) -> Optional[Dict[str, float]]:
        """Process telemetry point and return OEE KPIs if available"""
        timestamp = point.timestamp
        value = point.value
        tag = point.tag
        
        # Process availability data
        if tag in self.config.availability_tags:
            is_running = str(value).lower() in ['running', 'on', '1', 'true']
            self.availability_window.append((timestamp, is_running))
        
        # Process performance data
        elif tag in self.config.performance_tags:
            if isinstance(value, (int, float)):
                self.performance_window.append((timestamp, float(value)))
        
        # Process quality data
        elif tag in self.config.quality_tags:
            is_good = str(value).lower() in ['good', 'ok', '1', 'true']
            self.quality_window.append((timestamp, is_good))
        
        # Process cycle count
        elif tag == self.config.cycle_count_tag:
            if isinstance(value, (int, float)):
                self.cycle_count_history.append((timestamp, int(value)))
        
        # Calculate OEE if we have enough data
        if len(self.availability_window) > 10:  # Minimum data points
            return self.calculate_oee()
        
        return None
    
    def calculate_oee(self) -> Dict[str, float]:
        """Calculate OEE KPIs: Availability, Performance, Quality, and Overall OEE"""
        try:
            # Calculate Availability = (Running Time / Planned Production Time) * 100
            running_time = sum(1 for _, is_running in self.availability_window if is_running)
            availability = (running_time / len(self.availability_window)) * 100
            
            # Calculate Performance = (Actual Production Rate / Ideal Production Rate) * 100
            if self.performance_window and self.cycle_count_history:
                recent_performance = [val for _, val in list(self.performance_window)[-60:]]  # Last minute
                if recent_performance:
                    avg_actual_rate = statistics.mean(recent_performance)
                    # Assume ideal rate is 1.2x the average actual rate for demonstration
                    ideal_rate = avg_actual_rate * 1.2
                    performance = min((avg_actual_rate / ideal_rate) * 100, 100) if ideal_rate > 0 else 0
                else:
                    performance = 0
            else:
                performance = 0
            
            # Calculate Quality = (Good Units / Total Units) * 100
            if self.quality_window:
                good_units = sum(1 for _, is_good in self.quality_window if is_good)
                quality = (good_units / len(self.quality_window)) * 100
            else:
                quality = 100  # Default to 100% if no quality data
            
            # Calculate Overall OEE = Availability * Performance * Quality / 10000
            overall_oee = (availability * performance * quality) / 10000
            
            return {
                'availability': round(availability, 2),
                'performance': round(performance, 2),
                'quality': round(quality, 2),
                'overall_oee': round(overall_oee, 2),
                'running_time_percentage': round((running_time / len(self.availability_window)) * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating OEE: {e}")
            return {
                'availability': 0.0,
                'performance': 0.0,
                'quality': 0.0,
                'overall_oee': 0.0,
                'running_time_percentage': 0.0
            }


class EnergyKPIAnalytics:
    """Energy-focused KPI analytics processor for renewable energy, storage, and efficiency metrics"""
    
    def __init__(self, config: EnergyAnalyticsConfig):
        self.config = config
        self.efficiency_data = deque(maxlen=7200)  # 2 hours at 1-second intervals
        self.renewable_data = deque(maxlen=7200)
        self.battery_data = deque(maxlen=7200)
        self.load_data = deque(maxlen=7200)
        self.last_aggregation = datetime.utcnow()
        
        # Energy accumulation tracking
        self.renewable_energy_total = 0.0
        self.battery_energy_charged = 0.0
        self.battery_energy_discharged = 0.0
        self.load_energy_total = 0.0
        
    def process_telemetry(self, point: TelemetryPoint) -> Optional[Dict[str, float]]:
        """Process telemetry point and return energy KPI analytics"""
        timestamp = point.timestamp
        value = point.value
        tag = point.tag
        
        # Process efficiency data
        if tag in self.config.efficiency_tags and isinstance(value, (int, float)):
            self.efficiency_data.append((timestamp, float(value)))
        
        # Process renewable generation data
        elif tag in self.config.renewable_tags and isinstance(value, (int, float)):
            self.renewable_data.append((timestamp, float(value)))
        
        # Process battery storage data
        elif tag in self.config.battery_tags and isinstance(value, (int, float)):
            self.battery_data.append((timestamp, float(value)))
        
        # Process load consumption data
        elif tag in self.config.load_tags and isinstance(value, (int, float)):
            self.load_data.append((timestamp, float(value)))
        
        # Check if it's time to aggregate KPIs
        current_time = datetime.utcnow()
        if (current_time - self.last_aggregation).total_seconds() >= self.config.aggregation_interval:
            self.last_aggregation = current_time
            return self.calculate_energy_kpis()
        
        return None
    
    def calculate_energy_kpis(self) -> Dict[str, float]:
        """Calculate comprehensive energy KPIs"""
        try:
            kpis = {}
            
            # Renewable Generation KPIs
            if self.renewable_data:
                recent_renewable = [val for _, val in list(self.renewable_data)[-300:]]  # Last 5 minutes
                if recent_renewable:
                    avg_renewable = statistics.mean(recent_renewable)
                    peak_renewable = max(recent_renewable)
                    renewable_energy = (avg_renewable * self.config.aggregation_interval) / 3600
                    self.renewable_energy_total += renewable_energy
                    
                    kpis.update({
                        'avg_renewable_power_kw': round(avg_renewable, 3),
                        'peak_renewable_power_kw': round(peak_renewable, 3),
                        'renewable_energy_kwh': round(renewable_energy, 3),
                        'total_renewable_energy_kwh': round(self.renewable_energy_total, 3)
                    })
            
            # Battery Storage KPIs
            if self.battery_data:
                recent_battery = [val for _, val in list(self.battery_data)[-300:]]
                if recent_battery:
                    avg_soc = statistics.mean(recent_battery)
                    min_soc = min(recent_battery)
                    max_soc = max(recent_battery)
                    
                    # Calculate round-trip efficiency if we have charge/discharge data
                    round_trip_efficiency = self.calculate_battery_efficiency()
                    
                    kpis.update({
                        'avg_battery_soc_percent': round(avg_soc, 2),
                        'min_battery_soc_percent': round(min_soc, 2),
                        'max_battery_soc_percent': round(max_soc, 2),
                        'battery_round_trip_efficiency_percent': round(round_trip_efficiency, 2),
                        'battery_utilization_percent': round((max_soc - min_soc), 2)
                    })
            
            # Load Consumption KPIs
            if self.load_data:
                recent_load = [val for _, val in list(self.load_data)[-300:]]
                if recent_load:
                    avg_load = statistics.mean(recent_load)
                    peak_load = max(recent_load)
                    load_energy = (avg_load * self.config.aggregation_interval) / 3600
                    self.load_energy_total += load_energy
                    
                    # Load factor calculation
                    load_factor = (avg_load / peak_load) * 100 if peak_load > 0 else 0
                    
                    kpis.update({
                        'avg_load_power_kw': round(avg_load, 3),
                        'peak_load_power_kw': round(peak_load, 3),
                        'load_energy_kwh': round(load_energy, 3),
                        'total_load_energy_kwh': round(self.load_energy_total, 3),
                        'load_factor_percent': round(load_factor, 2)
                    })
            
            # System Efficiency KPIs
            if self.efficiency_data:
                recent_efficiency = [val for _, val in list(self.efficiency_data)[-300:]]
                if recent_efficiency:
                    avg_efficiency = statistics.mean(recent_efficiency)
                    kpis['avg_system_efficiency_percent'] = round(avg_efficiency, 2)
            
            # Renewable Share KPI
            if 'avg_renewable_power_kw' in kpis and 'avg_load_power_kw' in kpis:
                renewable_share = (kpis['avg_renewable_power_kw'] / 
                                 max(kpis['avg_load_power_kw'], 0.1)) * 100
                kpis['renewable_share_percent'] = round(min(renewable_share, 100), 2)
            
            # Energy Independence KPI
            if 'total_renewable_energy_kwh' in kpis and 'total_load_energy_kwh' in kpis:
                energy_independence = (kpis['total_renewable_energy_kwh'] / 
                                    max(kpis['total_load_energy_kwh'], 0.1)) * 100
                kpis['energy_independence_percent'] = round(min(energy_independence, 100), 2)
            
            return kpis
            
        except Exception as e:
            logger.error(f"Error calculating energy KPIs: {e}")
            return {}
    
    def calculate_battery_efficiency(self) -> float:
        """Calculate battery round-trip efficiency"""
        try:
            # This is a simplified calculation - in practice, you'd need charge/discharge energy data
            if self.battery_data:
                recent_soc = [val for _, val in list(self.battery_data)[-300:]]
                if len(recent_soc) > 60:  # Need at least 1 minute of data
                    soc_variance = statistics.stdev(recent_soc) if len(recent_soc) > 1 else 0
                    # Higher variance suggests active charging/discharging
                    # Assume 95% base efficiency with degradation based on variance
                    base_efficiency = 95.0
                    efficiency_penalty = min(soc_variance * 2, 10)  # Max 10% penalty
                    return base_efficiency - efficiency_penalty
            
            return 95.0  # Default battery efficiency
            
        except Exception as e:
            logger.error(f"Error calculating battery efficiency: {e}")
            return 95.0


class EnergyAnalytics:
    """Energy consumption and power factor analytics"""
    
    def __init__(self, config: EnergyMonitoringConfig):
        self.config = config
        self.power_data = deque(maxlen=7200)  # 2 hours at 1-second intervals
        self.voltage_data = deque(maxlen=7200)
        self.current_data = deque(maxlen=7200)
        self.energy_accumulator = defaultdict(float)
        self.last_aggregation = datetime.utcnow()
        
    def process_telemetry(self, point: TelemetryPoint) -> Optional[Dict[str, float]]:
        """Process telemetry point and return energy analytics"""
        timestamp = point.timestamp
        value = point.value
        tag = point.tag
        
        # Process power data
        if tag in self.config.power_tags and isinstance(value, (int, float)):
            self.power_data.append((timestamp, float(value)))
        
        # Process voltage data
        elif tag in self.config.voltage_tags and isinstance(value, (int, float)):
            self.voltage_data.append((timestamp, float(value)))
        
        # Process current data
        elif tag in self.config.current_tags and isinstance(value, (int, float)):
            self.current_data.append((timestamp, float(value)))
        
        # Check if it's time to aggregate
        current_time = datetime.utcnow()
        if (current_time - self.last_aggregation).total_seconds() >= self.config.aggregation_interval:
            self.last_aggregation = current_time
            return self.calculate_energy_metrics()
        
        return None
    
    def calculate_energy_metrics(self) -> Dict[str, float]:
        """Calculate energy consumption metrics"""
        try:
            # Calculate average power consumption
            if self.power_data:
                recent_power = [val for _, val in list(self.power_data)[-300:]]  # Last 5 minutes
                avg_power = statistics.mean(recent_power) if recent_power else 0
                
                # Calculate energy consumption (kWh) for the aggregation period
                energy_consumption = (avg_power * self.config.aggregation_interval) / 3600  # Convert to kWh
                
                # Calculate power factor if voltage and current data available
                power_factor = self.calculate_power_factor()
                
                # Accumulate energy
                self.energy_accumulator['total'] += energy_consumption
                
                return {
                    'avg_power_kw': round(avg_power, 3),
                    'energy_consumption_kwh': round(energy_consumption, 3),
                    'total_energy_kwh': round(self.energy_accumulator['total'], 3),
                    'power_factor': round(power_factor, 3),
                    'peak_power_kw': round(max(recent_power) if recent_power else 0, 3),
                    'min_power_kw': round(min(recent_power) if recent_power else 0, 3)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error calculating energy metrics: {e}")
            return {}
    
    def calculate_power_factor(self) -> float:
        """Calculate power factor from voltage and current data"""
        try:
            if self.voltage_data and self.current_data and self.power_data:
                # Get recent data
                recent_voltage = [val for _, val in list(self.voltage_data)[-60:]]
                recent_current = [val for _, val in list(self.current_data)[-60:]]
                recent_power = [val for _, val in list(self.power_data)[-60:]]
                
                if len(recent_voltage) == len(recent_current) == len(recent_power) and len(recent_voltage) > 0:
                    # Calculate apparent power (V * I)
                    apparent_powers = [v * i for v, i in zip(recent_voltage, recent_current)]
                    avg_apparent_power = statistics.mean(apparent_powers)
                    avg_real_power = statistics.mean(recent_power)
                    
                    # Power factor = Real Power / Apparent Power
                    if avg_apparent_power > 0:
                        return min(avg_real_power / avg_apparent_power, 1.0)
            
            return 0.95  # Default power factor
            
        except Exception as e:
            logger.error(f"Error calculating power factor: {e}")
            return 0.95


class PredictiveAnalytics:
    """Predictive maintenance analytics with energy-specific anomaly detection"""
    
    def __init__(self, config: PredictiveMaintenanceConfig):
        self.config = config
        self.data_windows = defaultdict(lambda: deque(maxlen=1800))  # 30-minute windows
        self.baseline_stats = defaultdict(dict)
        self.anomaly_threshold_multiplier = 2.5  # Standard deviations
        self.baseline_calculated = False
        
        # Energy-specific anomaly patterns
        self.energy_anomaly_patterns = {
            'battery_soc_drop': {'threshold': 20.0, 'window': 300},  # 20% SoC drop in 5 minutes
            'power_spike': {'threshold': 2.0, 'window': 60},       # 2x power spike in 1 minute
            'efficiency_drop': {'threshold': 15.0, 'window': 600},   # 15% efficiency drop in 10 minutes
            'voltage_deviation': {'threshold': 10.0, 'window': 120}   # 10% voltage deviation in 2 minutes
        }
        
    def process_telemetry(self, point: TelemetryPoint) -> Optional[Dict[str, Any]]:
        """Process telemetry point and return predictive analytics"""
        timestamp = point.timestamp
        value = point.value
        tag = point.tag
        
        # Check if this is a monitored tag
        monitored_tags = (self.config.vibration_tags + 
                         self.config.temperature_tags + 
                         self.config.pressure_tags)
        
        if tag in monitored_tags and isinstance(value, (int, float)):
            self.data_windows[tag].append((timestamp, float(value)))
            
            # Calculate baseline statistics if we have enough data
            if not self.baseline_calculated and len(self.data_windows[tag]) >= 900:  # 15 minutes
                self.calculate_baseline(tag)
            
            # Check for anomalies if baseline is calculated
            if self.baseline_calculated:
                return self.detect_anomalies(tag, value, timestamp)
        
        return None
    
    def calculate_baseline(self, tag: str):
        """Calculate baseline statistics for anomaly detection"""
        try:
            values = [val for _, val in self.data_windows[tag]]
            if len(values) >= 100:
                self.baseline_stats[tag] = {
                    'mean': statistics.mean(values),
                    'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                    'min': min(values),
                    'max': max(values),
                    'median': statistics.median(values),
                    'q75': np.percentile(values, 75),
                    'q25': np.percentile(values, 25)
                }
                
                # Check if all tags have baselines
                all_tags = (self.config.vibration_tags + 
                           self.config.temperature_tags + 
                           self.config.pressure_tags)
                if all(tag in self.baseline_stats for tag in all_tags):
                    self.baseline_calculated = True
                    logger.info("Baseline statistics calculated for all monitored tags")
                    
        except Exception as e:
            logger.error(f"Error calculating baseline for {tag}: {e}")
    
    def detect_anomalies(self, tag: str, current_value: float, timestamp: datetime) -> Dict[str, Any]:
        """Detect energy-specific anomalies using rolling window statistics"""
        try:
            if tag not in self.baseline_stats:
                return {}
            
            baseline = self.baseline_stats[tag]
            mean = baseline['mean']
            std_dev = baseline['std_dev']
            
            # Calculate z-score
            if std_dev > 0:
                z_score = abs(current_value - mean) / std_dev
            else:
                z_score = 0
            
            # Determine if anomaly
            is_anomaly = z_score > self.anomaly_threshold_multiplier
            
            # Check against configured thresholds
            threshold_anomaly = False
            if tag in self.config.maintenance_thresholds:
                threshold = self.config.maintenance_thresholds[tag]
                threshold_anomaly = current_value > threshold
            
            # Energy-specific anomaly detection
            energy_anomalies = self.detect_energy_anomalies(tag, current_value, timestamp)
            
            # Calculate trend (simple linear regression on last 30 points)
            trend = self.calculate_trend(tag)
            
            # Predictive maintenance score
            maintenance_score = self.calculate_maintenance_score(tag, current_value, z_score, trend)
            
            return {
                'tag': tag,
                'current_value': current_value,
                'baseline_mean': mean,
                'z_score': round(z_score, 3),
                'is_anomaly': is_anomaly,
                'threshold_anomaly': threshold_anomaly,
                'energy_anomalies': energy_anomalies,
                'trend': round(trend, 4),
                'maintenance_score': round(maintenance_score, 2),
                'prediction_horizon_hours': self.config.prediction_horizon,
                'timestamp': timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error detecting anomalies for {tag}: {e}")
            return {}
    
    def detect_energy_anomalies(self, tag: str, current_value: float, timestamp: datetime) -> Dict[str, Any]:
        """Detect energy-specific anomaly patterns"""
        anomalies = {}
        
        try:
            data_window = list(self.data_windows[tag])
            
            # Battery SoC rapid drop detection
            if 'soc' in tag.lower() or 'battery' in tag.lower():
                if len(data_window) >= 300:  # 5 minutes of data
                    recent_values = [val for _, val in data_window[-300:]]
                    older_values = [val for _, val in data_window[-600:-300]] if len(data_window) >= 600 else []
                    
                    if older_values:
                        avg_recent = statistics.mean(recent_values)
                        avg_older = statistics.mean(older_values)
                        soc_drop = avg_older - avg_recent
                        
                        if soc_drop > self.energy_anomaly_patterns['battery_soc_drop']['threshold']:
                            anomalies['battery_soc_drop'] = {
                                'detected': True,
                                'drop_percent': round(soc_drop, 2),
                                'severity': 'high' if soc_drop > 30 else 'medium'
                            }
            
            # Power spike detection
            elif 'power' in tag.lower():
                if len(data_window) >= 60:  # 1 minute of data
                    recent_values = [val for _, val in data_window[-60:]]
                    baseline_avg = statistics.mean([val for _, val in data_window[-300:-60]]) if len(data_window) >= 300 else current_value
                    
                    max_recent = max(recent_values)
                    spike_ratio = max_recent / baseline_avg if baseline_avg > 0 else 1
                    
                    if spike_ratio > self.energy_anomaly_patterns['power_spike']['threshold']:
                        anomalies['power_spike'] = {
                            'detected': True,
                            'spike_ratio': round(spike_ratio, 2),
                            'peak_power': round(max_recent, 3),
                            'severity': 'high' if spike_ratio > 3 else 'medium'
                        }
            
            # Efficiency drop detection
            elif 'efficiency' in tag.lower():
                if len(data_window) >= 600:  # 10 minutes of data
                    recent_values = [val for _, val in data_window[-300:]]
                    older_values = [val for _, val in data_window[-600:-300]]
                    
                    avg_recent = statistics.mean(recent_values)
                    avg_older = statistics.mean(older_values)
                    efficiency_drop = avg_older - avg_recent
                    
                    if efficiency_drop > self.energy_anomaly_patterns['efficiency_drop']['threshold']:
                        anomalies['efficiency_drop'] = {
                            'detected': True,
                            'drop_percent': round(efficiency_drop, 2),
                            'severity': 'high' if efficiency_drop > 25 else 'medium'
                        }
            
            # Voltage deviation detection
            elif 'voltage' in tag.lower():
                if len(data_window) >= 120:  # 2 minutes of data
                    recent_values = [val for _, val in data_window[-120:]]
                    baseline_avg = statistics.mean([val for _, val in data_window[-600:-120]]) if len(data_window) >= 600 else current_value
                    
                    avg_recent = statistics.mean(recent_values)
                    deviation_percent = abs(avg_recent - baseline_avg) / baseline_avg * 100 if baseline_avg > 0 else 0
                    
                    if deviation_percent > self.energy_anomaly_patterns['voltage_deviation']['threshold']:
                        anomalies['voltage_deviation'] = {
                            'detected': True,
                            'deviation_percent': round(deviation_percent, 2),
                            'severity': 'high' if deviation_percent > 15 else 'medium'
                        }
            
        except Exception as e:
            logger.error(f"Error detecting energy anomalies for {tag}: {e}")
        
        return anomalies
    
    def calculate_trend(self, tag: str) -> float:
        """Calculate trend using simple linear regression on recent data"""
        try:
            recent_data = list(self.data_windows[tag])[-30:]  # Last 30 points
            if len(recent_data) < 10:
                return 0.0
            
            # Simple linear regression: y = mx + b
            x_values = list(range(len(recent_data)))
            y_values = [val for _, val in recent_data]
            
            n = len(x_values)
            sum_x = sum(x_values)
            sum_y = sum(y_values)
            sum_xy = sum(x * y for x, y in zip(x_values, y_values))
            sum_x2 = sum(x * x for x in x_values)
            
            # Calculate slope (trend)
            if n * sum_x2 - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                return slope
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating trend for {tag}: {e}")
            return 0.0
    
    def calculate_maintenance_score(self, tag: str, current_value: float, 
                                  z_score: float, trend: float) -> float:
        """Calculate predictive maintenance score (0-100) with energy-specific weighting"""
        try:
            score = 0.0
            
            # Z-score component (0-30 points for energy systems)
            if z_score > 3:
                score += 30
            elif z_score > 2:
                score += 25
            elif z_score > 1:
                score += 15
            elif z_score > 0.5:
                score += 10
            
            # Trend component (0-25 points)
            if abs(trend) > 0.1:
                score += 25
            elif abs(trend) > 0.05:
                score += 18
            elif abs(trend) > 0.01:
                score += 12
            
            # Threshold component (0-25 points)
            if tag in self.config.maintenance_thresholds:
                threshold = self.config.maintenance_thresholds[tag]
                if current_value > threshold:
                    score += 25
                elif current_value > threshold * 0.9:
                    score += 18
                elif current_value > threshold * 0.8:
                    score += 12
            
            # Energy-specific criticality (0-20 points)
            if any(keyword in tag.lower() for keyword in ['battery', 'soc', 'temperature']):
                # Battery and temperature are critical for energy systems
                if current_value > 80:  # High temperature or low SoC
                    score += 20
                elif current_value > 70:
                    score += 15
                elif current_value > 60:
                    score += 10
            elif 'efficiency' in tag.lower():
                # Efficiency drops indicate performance issues
                if current_value < 70:  # Low efficiency
                    score += 20
                elif current_value < 80:
                    score += 15
                elif current_value < 85:
                    score += 10
            
            return min(score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating maintenance score for {tag}: {e}")
            return 0.0


class AnalyticsProcessor:
    """Main analytics processor that coordinates all analytics modules"""
    
    def __init__(self, asset_config: AssetConfiguration):
        self.asset_config = asset_config
        self.oee_analytics = None
        self.energy_analytics = None
        self.energy_kpi_analytics = None
        self.predictive_analytics = None
        
        # Initialize analytics modules based on configuration
        if asset_config.oee_monitoring:
            self.oee_analytics = OEEAnalytics(asset_config.oee_monitoring)
        
        if asset_config.energy_monitoring:
            self.energy_analytics = EnergyAnalytics(asset_config.energy_monitoring)
        
        if asset_config.energy_analytics:
            self.energy_kpi_analytics = EnergyKPIAnalytics(asset_config.energy_analytics)
        
        if asset_config.predictive_maintenance:
            self.predictive_analytics = PredictiveAnalytics(asset_config.predictive_maintenance)
        
        logger.info(f"Analytics processor initialized for {asset_config.asset_name}")
    
    async def process_telemetry_point(self, point: TelemetryPoint) -> Dict[str, Any]:
        """Process a single telemetry point and return analytics results"""
        results = {
            'asset_name': self.asset_config.asset_name,
            'timestamp': point.timestamp.isoformat(),
            'analytics': {}
        }
        
        # Process with OEE analytics (Legacy/Optional)
        if self.oee_analytics:
            oee_results = self.oee_analytics.process_telemetry(point)
            if oee_results:
                results['analytics']['oee'] = oee_results
        
        # Process with energy analytics
        if self.energy_analytics:
            energy_results = self.energy_analytics.process_telemetry(point)
            if energy_results:
                results['analytics']['energy'] = energy_results
        
        # Process with energy KPI analytics
        if self.energy_kpi_analytics:
            kpi_results = self.energy_kpi_analytics.process_telemetry(point)
            if kpi_results:
                results['analytics']['energy_kpis'] = kpi_results
        
        # Process with predictive analytics
        if self.predictive_analytics:
            predictive_results = self.predictive_analytics.process_telemetry(point)
            if predictive_results:
                results['analytics']['predictive'] = predictive_results
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of analytics processor"""
        status = {
            'asset_name': self.asset_config.asset_name,
            'modules': {
                'oee': self.oee_analytics is not None,
                'energy': self.energy_analytics is not None,
                'energy_kpis': self.energy_kpi_analytics is not None,
                'predictive': self.predictive_analytics is not None
            }
        }
        
        if self.predictive_analytics:
            status['baseline_calculated'] = self.predictive_analytics.baseline_calculated
        
        return status
