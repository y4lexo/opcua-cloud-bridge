"""Secure InfluxDB Cloud sender for OPC UA telemetry and analytics data"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

# Add parent directory to path for common models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import TelemetryPoint, Quality

logger = logging.getLogger(__name__)


class InfluxDBCloudSender:
    """Secure InfluxDB Cloud sender with ISA-95 field mapping"""
    
    def __init__(self, 
                 url: str = None,
                 token: str = None,
                 org: str = None,
                 bucket: str = None,
                 measurement_prefix: str = "opcua"):
        
        # Configuration from environment variables or parameters
        self.url = url or os.getenv("INFLUXDB_URL", "https://cloud2.influxdata.com")
        self.token = token or os.getenv("INFLUXDB_TOKEN")
        self.org = org or os.getenv("INFLUXDB_ORG", "globalcorp")
        self.bucket = bucket or os.getenv("INFLUXDB_BUCKET", "industrial-data")
        self.measurement_prefix = measurement_prefix
        
        # Client and write API
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        self.is_connected = False
        
        # Statistics
        self.stats = {
            'points_sent': 0,
            'points_failed': 0,
            'batches_sent': 0,
            'batches_failed': 0,
            'last_send_time': None,
            'connection_errors': 0
        }
        
        logger.info(f"InfluxDB Cloud sender initialized for org: {self.org}, bucket: {self.bucket}")
    
    async def connect(self) -> bool:
        """Connect to InfluxDB Cloud"""
        try:
            if not self.token:
                raise ValueError("InfluxDB token not provided. Set INFLUXDB_TOKEN environment variable.")
            
            # Create client with TLS configuration
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=30000,  # 30 seconds timeout
                verify_ssl=True  # Ensure TLS verification
            )
            
            # Test connection
            health = self.client.health()
            if health.status == "pass":
                self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
                self.is_connected = True
                logger.info(f"Connected to InfluxDB Cloud: {self.url}")
                return True
            else:
                logger.error(f"InfluxDB health check failed: {health.message}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB Cloud: {e}")
            self.stats['connection_errors'] += 1
            return False
    
    async def disconnect(self):
        """Disconnect from InfluxDB Cloud"""
        try:
            if self.client:
                self.client.close()
                self.is_connected = False
                logger.info("Disconnected from InfluxDB Cloud")
        except Exception as e:
            logger.error(f"Error disconnecting from InfluxDB: {e}")
    
    def telemetry_to_point(self, telemetry: Dict[str, Any]) -> Point:
        """Convert telemetry data to InfluxDB Point with ISA-95 mapping"""
        try:
            # Extract telemetry fields
            timestamp = telemetry.get('timestamp', datetime.utcnow())
            enterprise = telemetry.get('enterprise', 'unknown')
            site = telemetry.get('site', 'unknown')
            area = telemetry.get('area', 'unknown')
            line = telemetry.get('line', 'unknown')
            machine = telemetry.get('machine', 'unknown')
            tag = telemetry.get('tag', 'unknown')
            value = telemetry.get('value')
            unit = telemetry.get('unit')
            quality = telemetry.get('quality', 'GOOD')
            
            # Create point with ISA-95 hierarchy as tags
            point = Point(f"{self.measurement_prefix}_telemetry") \
                .time(timestamp) \
                .tag("enterprise", enterprise) \
                .tag("site", site) \
                .tag("area", area) \
                .tag("line", line) \
                .tag("machine", machine) \
                .tag("tag", tag) \
                .tag("quality", quality)
            
            # Add unit as tag if available
            if unit:
                point = point.tag("unit", unit)
            
            # Add value as field
            if isinstance(value, (int, float)):
                point = point.field("value_float", float(value))
            elif isinstance(value, bool):
                point = point.field("value_bool", value)
            else:
                point = point.field("value_string", str(value))
            
            return point
            
        except Exception as e:
            logger.error(f"Error converting telemetry to point: {e}")
            raise
    
    def analytics_to_point(self, analytics: Dict[str, Any]) -> List[Point]:
        """Convert analytics data to InfluxDB Points"""
        points = []
        
        try:
            timestamp = analytics.get('timestamp', datetime.utcnow())
            asset_name = analytics.get('asset_name', 'unknown')
            analytics_data = analytics.get('analytics', {})
            
            # Create points for each analytics type
            for analytics_type, data in analytics_data.items():
                if not data or not isinstance(data, dict):
                    continue
                
                # Create base point
                point = Point(f"{self.measurement_prefix}_analytics") \
                    .time(timestamp) \
                    .tag("asset_name", asset_name) \
                    .tag("analytics_type", analytics_type)
                
                # Add analytics data as fields
                for key, value in data.items():
                    if isinstance(value, (int, float)):
                        point = point.field(f"{key}", float(value))
                    elif isinstance(value, bool):
                        point = point.field(f"{key}", value)
                    elif isinstance(value, str):
                        point = point.field(f"{key}", value)
                    elif isinstance(value, dict):
                        # Handle nested objects (e.g., predictive analytics)
                        for nested_key, nested_value in value.items():
                            if isinstance(nested_value, (int, float)):
                                point = point.field(f"{key}_{nested_key}", float(nested_value))
                            elif isinstance(nested_value, bool):
                                point = point.field(f"{key}_{nested_key}", nested_value)
                            else:
                                point = point.field(f"{key}_{nested_key}", str(nested_value))
                
                points.append(point)
            
            return points
            
        except Exception as e:
            logger.error(f"Error converting analytics to points: {e}")
            return []
    
    async def send_telemetry_batch(self, telemetry_batch: List[Dict[str, Any]]) -> bool:
        """Send batch of telemetry points to InfluxDB Cloud"""
        if not self.is_connected or not telemetry_batch:
            return False
        
        try:
            # Convert telemetry to points
            points = []
            for telemetry in telemetry_batch:
                point = self.telemetry_to_point(telemetry)
                points.append(point)
            
            # Send points
            await self._send_points_async(points)
            
            self.stats['batches_sent'] += 1
            self.stats['points_sent'] += len(points)
            self.stats['last_send_time'] = datetime.utcnow()
            
            logger.info(f"Sent telemetry batch: {len(points)} points")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send telemetry batch: {e}")
            self.stats['batches_failed'] += 1
            self.stats['points_failed'] += len(telemetry_batch)
            return False
    
    async def send_analytics_batch(self, analytics_batch: List[Dict[str, Any]]) -> bool:
        """Send batch of analytics points to InfluxDB Cloud"""
        if not self.is_connected or not analytics_batch:
            return False
        
        try:
            # Convert analytics to points
            points = []
            for analytics in analytics_batch:
                analytics_points = self.analytics_to_point(analytics)
                points.extend(analytics_points)
            
            # Send points
            await self._send_points_async(points)
            
            self.stats['batches_sent'] += 1
            self.stats['points_sent'] += len(points)
            self.stats['last_send_time'] = datetime.utcnow()
            
            logger.info(f"Sent analytics batch: {len(points)} points")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send analytics batch: {e}")
            self.stats['batches_failed'] += 1
            self.stats['points_failed'] += len(analytics_batch)
            return False
    
    async def send_mixed_batch(self, telemetry_batch: List[Dict[str, Any]], 
                             analytics_batch: List[Dict[str, Any]]) -> bool:
        """Send mixed batch of telemetry and analytics points"""
        if not self.is_connected or (not telemetry_batch and not analytics_batch):
            return False
        
        try:
            # Convert all data to points
            points = []
            
            # Add telemetry points
            for telemetry in telemetry_batch:
                point = self.telemetry_to_point(telemetry)
                points.append(point)
            
            # Add analytics points
            for analytics in analytics_batch:
                analytics_points = self.analytics_to_point(analytics)
                points.extend(analytics_points)
            
            # Send all points
            await self._send_points_async(points)
            
            self.stats['batches_sent'] += 1
            self.stats['points_sent'] += len(points)
            self.stats['last_send_time'] = datetime.utcnow()
            
            logger.info(f"Sent mixed batch: {len(telemetry_batch)} telemetry, {len(analytics_batch)} analytics, {len(points)} total points")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send mixed batch: {e}")
            self.stats['batches_failed'] += 1
            total_points = len(telemetry_batch) + len(analytics_batch)
            self.stats['points_failed'] += total_points
            return False
    
    async def _send_points_async(self, points: List[Point]):
        """Send points to InfluxDB asynchronously"""
        try:
            # Use asyncio to run the synchronous write operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.write_api.write, self.bucket, points)
        except Exception as e:
            logger.error(f"Error sending points to InfluxDB: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test connection to InfluxDB Cloud"""
        try:
            if not self.is_connected:
                return await self.connect()
            
            # Create test point
            test_point = Point("connection_test") \
                .tag("source", "opcua-edge-collector") \
                .field("test_value", 1.0) \
                .time(datetime.utcnow())
            
            # Send test point
            await self._send_points_async([test_point])
            
            logger.info("InfluxDB connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"InfluxDB connection test failed: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sender statistics"""
        stats = self.stats.copy()
        stats['is_connected'] = self.is_connected
        stats['url'] = self.url
        stats['org'] = self.org
        stats['bucket'] = self.bucket
        
        # Calculate success rate
        total_batches = stats['batches_sent'] + stats['batches_failed']
        if total_batches > 0:
            stats['success_rate'] = (stats['batches_sent'] / total_batches) * 100
        else:
            stats['success_rate'] = 0.0
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {}
        }
        
        try:
            # Check connection
            if self.is_connected:
                health_status['checks']['connection'] = 'pass'
            else:
                health_status['checks']['connection'] = 'fail'
                health_status['status'] = 'unhealthy'
            
            # Check InfluxDB health
            if self.client:
                try:
                    influx_health = self.client.health()
                    if influx_health.status == "pass":
                        health_status['checks']['influxdb'] = 'pass'
                    else:
                        health_status['checks']['influxdb'] = 'fail'
                        health_status['status'] = 'degraded'
                except:
                    health_status['checks']['influxdb'] = 'fail'
                    health_status['status'] = 'unhealthy'
            
            # Check recent activity
            if self.stats['last_send_time']:
                time_since_last = (datetime.utcnow() - self.stats['last_send_time']).total_seconds()
                if time_since_last > 300:  # 5 minutes
                    health_status['checks']['activity'] = 'stale'
                    health_status['status'] = 'degraded'
                else:
                    health_status['checks']['activity'] = 'pass'
            else:
                health_status['checks']['activity'] = 'no_data'
            
            # Add statistics
            health_status['statistics'] = self.get_statistics()
            
        except Exception as e:
            health_status['status'] = 'error'
            health_status['error'] = str(e)
        
        return health_status


# Factory function for easy instantiation
def create_influxdb_sender() -> InfluxDBCloudSender:
    """Create InfluxDB sender from environment variables"""
    return InfluxDBCloudSender()
