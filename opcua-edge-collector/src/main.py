"""Main orchestration for OPC UA Edge Collector"""

import asyncio
import logging
import signal
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for common models
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import BridgeConfiguration, AssetConfiguration, TelemetryPoint
from opcua_client import OPCUAClient
from analytics_processor import AnalyticsProcessor
from data_buffer import DataBuffer, get_data_buffer
from cloud_sender import InfluxDBCloudSender, create_influxdb_sender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('edge_collector.log')
    ]
)

logger = logging.getLogger(__name__)


class EdgeCollectorOrchestrator:
    """Main orchestrator for OPC UA Edge Collector"""
    
    def __init__(self, config_path: str = "../../use_case_config.yaml"):
        self.config_path = config_path
        self.config: Optional[BridgeConfiguration] = None
        
        # Components
        self.opcua_client: Optional[OPCUAClient] = None
        self.analytics_processors: Dict[str, AnalyticsProcessor] = {}
        self.data_buffer: Optional[DataBuffer] = None
        self.cloud_sender: Optional[InfluxDBCloudSender] = None
        
        # Runtime state
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Configuration
        self.buffer_send_interval = 30  # seconds
        self.buffer_batch_size = 100
        self.analytics_batch_size = 50
        self.max_retry_attempts = 3
        self.retry_delay = 5  # seconds
        
        logger.info("Edge Collector Orchestrator initialized")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing Edge Collector components...")
            
            # Load configuration
            await self._load_configuration()
            
            # Initialize data buffer
            await self._initialize_buffer()
            
            # Initialize cloud sender
            await self._initialize_cloud_sender()
            
            # Initialize OPC UA client
            await self._initialize_opcua_client()
            
            # Initialize analytics processors
            await self._initialize_analytics_processors()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def _load_configuration(self):
        """Load configuration from YAML file"""
        try:
            config_file = Path(__file__).parent / self.config_path
            with open(config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            self.config = BridgeConfiguration(**config_data)
            logger.info(f"Configuration loaded: {self.config.enterprise_name}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    async def _initialize_buffer(self):
        """Initialize local data buffer"""
        try:
            self.data_buffer = DataBuffer(
                db_path="edge_buffer.db",
                max_size_mb=200  # 200MB buffer
            )
            await self.data_buffer.initialize()
            logger.info("Data buffer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize buffer: {e}")
            raise
    
    async def _initialize_cloud_sender(self):
        """Initialize InfluxDB Cloud sender"""
        try:
            self.cloud_sender = create_influxdb_sender()
            
            # Test connection
            if not await self.cloud_sender.connect():
                raise ConnectionError("Failed to connect to InfluxDB Cloud")
            
            logger.info("Cloud sender initialized and connected")
        except Exception as e:
            logger.error(f"Failed to initialize cloud sender: {e}")
            raise
    
    async def _initialize_opcua_client(self):
        """Initialize OPC UA client"""
        try:
            self.opcua_client = OPCUAClient(self.config_path)
            
            # Add data callback
            self.opcua_client.add_data_callback(self._handle_telemetry_data)
            
            logger.info("OPC UA client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OPC UA client: {e}")
            raise
    
    async def _initialize_analytics_processors(self):
        """Initialize analytics processors for each asset"""
        try:
            if not self.config:
                raise ValueError("Configuration not loaded")
            
            for site in self.config.sites:
                for asset in site.assets:
                    processor = AnalyticsProcessor(asset)
                    self.analytics_processors[asset.asset_name] = processor
                    logger.info(f"Analytics processor initialized for {asset.asset_name}")
            
            logger.info(f"Initialized {len(self.analytics_processors)} analytics processors")
        except Exception as e:
            logger.error(f"Failed to initialize analytics processors: {e}")
            raise
    
    def _handle_telemetry_data(self, telemetry_point: TelemetryPoint):
        """Handle incoming telemetry data"""
        try:
            # This is called from the OPC UA client callback
            # We need to handle this asynchronously
            asyncio.create_task(self._process_telemetry_async(telemetry_point))
        except Exception as e:
            logger.error(f"Error handling telemetry data: {e}")
    
    async def _process_telemetry_async(self, telemetry_point: TelemetryPoint):
        """Process telemetry point asynchronously"""
        try:
            # Process with analytics
            if telemetry_point.machine in self.analytics_processors:
                processor = self.analytics_processors[telemetry_point.machine]
                analytics_results = await processor.process_telemetry_point(telemetry_point)
                
                # Save analytics results to buffer
                if analytics_results and analytics_results.get('analytics'):
                    await self.data_buffer.save_analytics_result(analytics_results)
            
            # Save telemetry to buffer
            await self.data_buffer.save_telemetry_point(telemetry_point)
            
            logger.debug(f"Processed telemetry: {telemetry_point.machine}.{telemetry_point.tag}")
            
        except Exception as e:
            logger.error(f"Error processing telemetry: {e}")
    
    async def _buffer_sender_loop(self):
        """Main loop for sending buffered data to cloud"""
        logger.info("Starting buffer sender loop")
        
        while self.is_running:
            try:
                # Wait for interval or shutdown
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(), 
                        timeout=self.buffer_send_interval
                    )
                    if self.shutdown_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass  # Continue with normal operation
                
                # Get telemetry batch
                telemetry_batch = await self.data_buffer.get_telemetry_batch(
                    batch_size=self.buffer_batch_size
                )
                
                # Get analytics batch
                analytics_batch = await self.data_buffer.get_analytics_batch(
                    batch_size=self.analytics_batch_size
                )
                
                if telemetry_batch or analytics_batch:
                    # Generate batch ID
                    batch_id = str(uuid.uuid4())
                    
                    # Mark batch as being processed
                    for item in telemetry_batch:
                        item['batch_id'] = batch_id
                    for item in analytics_batch:
                        item['batch_id'] = batch_id
                    
                    # Send to cloud with retry logic
                    success = await self._send_batch_with_retry(
                        telemetry_batch, analytics_batch, batch_id
                    )
                    
                    if success:
                        # Mark batch as processed and delete
                        await self.data_buffer.mark_batch_processed(batch_id)
                        await self.data_buffer.delete_batch(batch_id)
                        logger.info(f"Successfully sent and deleted batch {batch_id}")
                    else:
                        logger.warning(f"Failed to send batch {batch_id}, will retry later")
                else:
                    logger.debug("No data to send")
                
            except Exception as e:
                logger.error(f"Error in buffer sender loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
        
        logger.info("Buffer sender loop stopped")
    
    async def _send_batch_with_retry(self, telemetry_batch: List[Dict], 
                                   analytics_batch: List[Dict], 
                                   batch_id: str) -> bool:
        """Send batch with retry logic"""
        for attempt in range(self.max_retry_attempts):
            try:
                # Test connection before sending
                if not await self.cloud_sender.test_connection():
                    logger.warning(f"InfluxDB connection test failed, attempt {attempt + 1}")
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        return False
                
                # Send batch
                success = await self.cloud_sender.send_mixed_batch(
                    telemetry_batch, analytics_batch
                )
                
                if success:
                    return True
                else:
                    logger.warning(f"Failed to send batch {batch_id}, attempt {attempt + 1}")
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                
            except Exception as e:
                logger.error(f"Error sending batch {batch_id}, attempt {attempt + 1}: {e}")
                if attempt < self.max_retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        return False
    
    async def _health_monitor_loop(self):
        """Health monitoring and maintenance loop"""
        logger.info("Starting health monitor loop")
        
        while self.is_running:
            try:
                # Wait for interval or shutdown
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(), 
                        timeout=300  # 5 minutes
                    )
                    if self.shutdown_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass  # Continue with normal operation
                
                # Check component health
                health_status = await self._check_component_health()
                
                # Log health status
                if health_status['overall'] != 'healthy':
                    logger.warning(f"Health check failed: {health_status}")
                
                # Perform maintenance
                await self._perform_maintenance()
                
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
        
        logger.info("Health monitor loop stopped")
    
    async def _check_component_health(self) -> Dict[str, Any]:
        """Check health of all components"""
        health_status = {
            'overall': 'healthy',
            'components': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Check OPC UA client
            if self.opcua_client and self.opcua_client.is_running:
                health_status['components']['opcua_client'] = 'healthy'
            else:
                health_status['components']['opcua_client'] = 'unhealthy'
                health_status['overall'] = 'degraded'
            
            # Check data buffer
            if self.data_buffer:
                buffer_status = await self.data_buffer.get_buffer_status()
                health_status['components']['data_buffer'] = 'healthy'
                health_status['buffer_stats'] = buffer_status
            else:
                health_status['components']['data_buffer'] = 'unhealthy'
                health_status['overall'] = 'degraded'
            
            # Check cloud sender
            if self.cloud_sender:
                sender_health = await self.cloud_sender.health_check()
                health_status['components']['cloud_sender'] = sender_health['status']
                health_status['sender_stats'] = sender_health.get('statistics', {})
                
                if sender_health['status'] != 'healthy':
                    health_status['overall'] = 'degraded'
            else:
                health_status['components']['cloud_sender'] = 'unhealthy'
                health_status['overall'] = 'degraded'
            
            # Check analytics processors
            healthy_processors = 0
            for asset_name, processor in self.analytics_processors.items():
                try:
                    status = processor.get_status()
                    if status:
                        healthy_processors += 1
                except:
                    pass
            
            if healthy_processors == len(self.analytics_processors):
                health_status['components']['analytics_processors'] = 'healthy'
            else:
                health_status['components']['analytics_processors'] = 'degraded'
                health_status['overall'] = 'degraded'
            
        except Exception as e:
            health_status['overall'] = 'error'
            health_status['error'] = str(e)
        
        return health_status
    
    async def _perform_maintenance(self):
        """Perform maintenance tasks"""
        try:
            # Clean up old processed data
            deleted_count = await self.data_buffer.delete_processed_batches(older_than_hours=24)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old processed batches")
            
            # Log statistics
            if self.cloud_sender:
                stats = self.cloud_sender.get_statistics()
                logger.info(f"Cloud sender stats: {stats}")
            
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
    
    async def start(self):
        """Start the edge collector"""
        try:
            logger.info("Starting OPC UA Edge Collector...")
            
            # Initialize components
            await self.initialize()
            
            self.is_running = True
            
            # Start all concurrent tasks
            tasks = [
                # OPC UA client (runs indefinitely)
                self.opcua_client.start(),
                
                # Buffer sender loop
                self._buffer_sender_loop(),
                
                # Health monitor loop
                self._health_monitor_loop()
            ]
            
            logger.info("Edge Collector started successfully")
            
            # Wait for all tasks to complete (or shutdown)
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        except Exception as e:
            logger.error(f"Edge collector error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the edge collector"""
        logger.info("Stopping OPC UA Edge Collector...")
        
        self.is_running = False
        self.shutdown_event.set()
        
        # Stop components
        if self.opcua_client:
            await self.opcua_client.stop()
        
        if self.cloud_sender:
            await self.cloud_sender.disconnect()
        
        if self.data_buffer:
            await self.data_buffer.close()
        
        logger.info("Edge Collector stopped")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point"""
    orchestrator = EdgeCollectorOrchestrator()
    orchestrator.setup_signal_handlers()
    
    try:
        await orchestrator.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
