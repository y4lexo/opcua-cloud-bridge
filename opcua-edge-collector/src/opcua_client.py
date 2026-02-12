"""Asynchronous OPC UA client with X.509 certificate security"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import yaml
from asyncua import Client, ua
from asyncua.common.methods import uamethod

# Add parent directory to path for common models
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import BridgeConfiguration, AssetConfiguration, TelemetryPoint, Quality
from config import load_config, get_connection_settings

logger = logging.getLogger(__name__)


class OPCUAClient:
    """Secure OPC UA client with X.509 certificate authentication"""
    
    def __init__(self, config_path: str = "../../use_case_config.yaml"):
        self.config_path = config_path
        self.config: Optional[BridgeConfiguration] = None
        self.clients: Dict[str, Client] = {}
        self.subscriptions: Dict[str, Any] = {}
        self.node_cache: Dict[str, Any] = {}
        self.data_callbacks: List[Callable[[TelemetryPoint], None]] = []
        self.is_running = False
        
        # Connection management
        self.connection_attempts: Dict[str, int] = {}
        self.last_connection_attempt: Dict[str, float] = {}
        self.max_retry_attempts = 5
        self.base_retry_delay = 1.0  # Base delay for exponential backoff
        self.max_retry_delay = 60.0  # Maximum delay
        
        # Security settings
        self.cert_dir = Path("../../opcua-server-sim/certs")
        self.client_cert_file = self.cert_dir / "client_cert.der"
        self.client_key_file = self.cert_dir / "client_private_key.pem"
        self.trust_store = self.cert_dir / "trust" / "trust.der"
        
        logger.info("OPC UA Client initialized with enhanced reconnection strategy")
    
    async def load_config(self) -> BridgeConfiguration:
        """Load configuration from YAML file with environment overrides"""
        try:
            self.config = load_config()
            logger.info(f"Loaded configuration for enterprise: {self.config.enterprise_name}")
            
            # Update connection settings from config
            conn_settings = get_connection_settings()
            self.max_retry_attempts = conn_settings.get('retry_attempts', 5)
            self.base_retry_delay = conn_settings.get('retry_delay', 1.0)
            
            return self.config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    async def setup_security(self, client: Client, endpoint: str, asset: Optional[AssetConfiguration] = None) -> Client:
        """Setup security for OPC UA client with dynamic policy negotiation"""
        try:
            # Determine security policy
            security_policy = await self._negotiate_security_policy(endpoint, asset)
            
            # Generate client certificates if they don't exist
            await self._ensure_client_certificates()
            
            if security_policy == "None":
                # No security for older PLCs
                client.set_security_string("None")
                logger.info(f"Using no security for endpoint: {endpoint}")
            else:
                # Setup certificate-based security
                security_string = f"{security_policy},SignAndEncrypt,{self.client_cert_file},{self.client_key_file}"
                client.set_security_string(security_string)
                
                # Set trust store
                if self.trust_store.exists():
                    await client.load_trust_store(str(self.trust_store))
                
                # Set user identity (certificate-based)
                client.set_user_identity_certificate(
                    str(self.client_cert_file), 
                    str(self.client_key_file)
                )
                
                logger.info(f"Using security policy {security_policy} for endpoint: {endpoint}")
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to setup security for {endpoint}: {e}")
            raise
    
    async def _ensure_client_certificates(self):
        """Generate client certificates if they don't exist"""
        if not self.client_cert_file.exists() or not self.client_key_file.exists():
            logger.info("Generating client certificates...")
            
            # Import certificate generation utilities
            from cert_utils import generate_self_signed_certificate
            
            cert_file, key_file = generate_self_signed_certificate(
                cert_dir=str(self.cert_dir),
                server_name="OPCUA-Edge-Collector-Client"
            )
            
            # Copy to client certificate names
            import shutil
            shutil.copy2(cert_file, self.client_cert_file)
            shutil.copy2(key_file, self.client_key_file)
            
            logger.info("Client certificates generated")
    
    async def _negotiate_security_policy(self, endpoint: str, asset: Optional[AssetConfiguration] = None) -> str:
        """Negotiate security policy with the server"""
        # Check for explicit policy in configuration
        if asset and hasattr(asset, 'security_settings'):
            explicit_policy = asset.security_settings.get('security_policy')
            if explicit_policy:
                return explicit_policy
        
        # Check environment variable override
        env_policy = os.getenv('OPCUA_SECURITY_POLICY')
        if env_policy:
            return env_policy
        
        # Try to negotiate with server
        try:
            # Create a temporary client to discover endpoints
            temp_client = Client(url=endpoint)
            
            # Try with no security first to get endpoints
            temp_client.set_security_string("None")
            await temp_client.connect()
            
            # Get available endpoints
            endpoints = await temp_client.get_endpoints()
            await temp_client.disconnect()
            
            # Prefer Basic256Sha256 if available, fallback to None
            for endpoint_desc in endpoints:
                if hasattr(endpoint_desc, 'SecurityPolicyUri'):
                    if 'Basic256Sha256' in endpoint_desc.SecurityPolicyUri:
                        return 'Basic256Sha256'
                    elif 'Basic128Rsa15' in endpoint_desc.SecurityPolicyUri:
                        return 'Basic128Rsa15'
            
            # Fallback to no security
            logger.warning(f"No compatible security policy found for {endpoint}, using None")
            return "None"
            
        except Exception as e:
            logger.warning(f"Failed to negotiate security policy for {endpoint}: {e}, using None")
            return "None"
    
    def _calculate_retry_delay(self, asset_name: str) -> float:
        """Calculate exponential backoff delay for reconnection"""
        attempt = self.connection_attempts.get(asset_name, 0)
        delay = min(self.base_retry_delay * (2 ** attempt), self.max_retry_delay)
        
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0.1, 0.3) * delay
        
        return delay + jitter
    
    async def _should_retry_connection(self, asset_name: str) -> bool:
        """Check if we should retry connection to an asset"""
        attempt = self.connection_attempts.get(asset_name, 0)
        
        if attempt >= self.max_retry_attempts:
            return False
        
        # Check if enough time has passed since last attempt
        last_attempt = self.last_connection_attempt.get(asset_name, 0)
        retry_delay = self._calculate_retry_delay(asset_name)
        
        return (time.time() - last_attempt) >= retry_delay
    
    async def connect_to_asset(self, asset: AssetConfiguration) -> bool:
        """Connect to a single asset's OPC UA server with exponential backoff"""
        asset_name = asset.asset_name
        
        # Check if we should retry
        if not await self._should_retry_connection(asset_name):
            logger.warning(f"Max retry attempts reached for {asset_name}, giving up")
            return False
        
        try:
            endpoint = asset.opcua_endpoint
            logger.info(f"Connecting to asset: {asset_name} at {endpoint} (attempt {self.connection_attempts.get(asset_name, 0) + 1})")
            
            # Update connection attempt tracking
            self.connection_attempts[asset_name] = self.connection_attempts.get(asset_name, 0) + 1
            self.last_connection_attempt[asset_name] = time.time()
            
            # Create client
            client = Client(url=endpoint)
            
            # Setup security with dynamic negotiation
            client = await self.setup_security(client, endpoint, asset)
            
            # Set connection timeout
            conn_settings = get_connection_settings()
            timeout = conn_settings.get('connection_timeout', 10.0)
            client.set_timeout(timeout)
            
            # Connect
            await client.connect()
            
            # Store client and reset connection attempts on success
            self.clients[asset_name] = client
            self.connection_attempts[asset_name] = 0
            
            logger.info(f"Successfully connected to {asset_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {asset_name}: {e}")
            
            # Calculate next retry delay
            retry_delay = self._calculate_retry_delay(asset_name)
            logger.info(f"Next retry for {asset_name} in {retry_delay:.1f} seconds")
            
            return False
    
    async def disconnect_from_asset(self, asset_name: str):
        """Disconnect from a specific asset"""
        try:
            if asset_name in self.clients:
                client = self.clients[asset_name]
                await client.disconnect()
                del self.clients[asset_name]
                logger.info(f"Disconnected from {asset_name}")
        except Exception as e:
            logger.error(f"Error disconnecting from {asset_name}: {e}")
    
    async def subscribe_to_asset(self, asset: AssetConfiguration) -> bool:
        """Subscribe to all configured tags for an asset"""
        try:
            if asset.asset_name not in self.clients:
                logger.error(f"Client not connected for asset: {asset.asset_name}")
                return False
            
            client = self.clients[asset.asset_name]
            
            # Get namespace index
            uri = "http://globalcorp.com/opcua/simulation"
            ns_idx = await client.get_namespace_index(uri)
            
            # Create subscription
            handler = DataChangeHandler(asset, self.data_callbacks)
            subscription = await client.create_subscription(1000, handler)  # 1 second publishing interval
            
            # Subscribe to all configured nodes
            subscribed_nodes = 0
            
            for tag_name, node_id in asset.node_mapping.items():
                try:
                    # Parse node ID (handle both string and numeric formats)
                    if node_id.startswith("ns="):
                        # Full namespace format like "ns=2;i=1001"
                        node = await client.get_node(node_id)
                    else:
                        # Simple format, add namespace
                        if node_id.isdigit():
                            node_id_full = f"ns={ns_idx};i={node_id}"
                        else:
                            node_id_full = f"ns={ns_idx};s={node_id}"
                        node = await client.get_node(node_id_full)
                    
                    # Subscribe to data changes
                    await subscription.subscribe_data_change(node)
                    
                    # Cache node reference
                    cache_key = f"{asset.asset_name}.{tag_name}"
                    self.node_cache[cache_key] = node
                    
                    subscribed_nodes += 1
                    logger.debug(f"Subscribed to {asset.asset_name}.{tag_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to subscribe to {asset.asset_name}.{tag_name}: {e}")
            
            # Store subscription
            self.subscriptions[asset.asset_name] = subscription
            
            logger.info(f"Subscribed to {subscribed_nodes} tags for {asset.asset_name}")
            return subscribed_nodes > 0
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {asset.asset_name}: {e}")
            return False
    
    async def read_all_nodes(self, asset: AssetConfiguration) -> List[TelemetryPoint]:
        """Read current values from all configured nodes"""
        telemetry_points = []
        
        try:
            if asset.asset_name not in self.clients:
                logger.error(f"Client not connected for asset: {asset.asset_name}")
                return telemetry_points
            
            client = self.clients[asset.asset_name]
            
            for tag_name, node_id in asset.node_mapping.items():
                try:
                    cache_key = f"{asset.asset_name}.{tag_name}"
                    if cache_key in self.node_cache:
                        node = self.node_cache[cache_key]
                    else:
                        # Get node if not cached
                        if node_id.startswith("ns="):
                            node = await client.get_node(node_id)
                        else:
                            ns_idx = await client.get_namespace_index("http://globalcorp.com/opcua/simulation")
                            if node_id.isdigit():
                                node_id_full = f"ns={ns_idx};i={node_id}"
                            else:
                                node_id_full = f"ns={ns_idx};s={node_id}"
                            node = await client.get_node(node_id_full)
                        
                        self.node_cache[cache_key] = node
                    
                    # Read value
                    data_value = await node.read_data_value()
                    value = data_value.Value.Value
                    
                    # Create telemetry point
                    telemetry_point = TelemetryPoint(
                        timestamp=datetime.utcnow(),
                        enterprise=self.config.enterprise_name,
                        site=asset.metadata.get('site', 'Unknown'),
                        area=asset.metadata.get('area', 'Unknown'),
                        line=asset.metadata.get('line', 'Unknown'),
                        machine=asset.asset_name,
                        tag=tag_name,
                        value=value,
                        unit=None,  # Could be enhanced to read from node properties
                        quality=Quality.GOOD  # Could be enhanced to read actual quality
                    )
                    
                    telemetry_points.append(telemetry_point)
                    
                except Exception as e:
                    logger.error(f"Failed to read {asset.asset_name}.{tag_name}: {e}")
            
            return telemetry_points
            
        except Exception as e:
            logger.error(f"Failed to read nodes for {asset.asset_name}: {e}")
            return telemetry_points
    
    def add_data_callback(self, callback: Callable[[TelemetryPoint], None]):
        """Add callback function for received data"""
        self.data_callbacks.append(callback)
    
    async def start(self):
        """Start the OPC UA client and connect to all assets"""
        try:
            # Load configuration
            await self.load_config()
            
            if not self.config:
                raise ValueError("Configuration not loaded")
            
            self.is_running = True
            connected_assets = []
            
            # Connect to all assets
            for site in self.config.sites:
                for asset in site.assets:
                    if await self.connect_to_asset(asset):
                        connected_assets.append(asset)
            
            # Subscribe to all connected assets
            subscribed_assets = []
            for asset in connected_assets:
                if await self.subscribe_to_asset(asset):
                    subscribed_assets.append(asset)
            
            logger.info(f"OPC UA Client started: {len(subscribed_assets)} assets connected and subscribed")
            
            # Keep running with enhanced reconnection logic
            try:
                while self.is_running:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    
                    # Reconnection logic with exponential backoff
                    for site in self.config.sites:
                        for asset in site.assets:
                            asset_name = asset.asset_name
                            
                            # Check if asset is disconnected
                            if asset_name not in self.clients:
                                # Check if we should retry
                                if await self._should_retry_connection(asset_name):
                                    logger.info(f"Attempting to reconnect to {asset_name}")
                                    if await self.connect_to_asset(asset):
                                        await self.subscribe_to_asset(asset)
                            else:
                                # Check if existing connection is still alive
                                try:
                                    client = self.clients[asset_name]
                                    # Simple health check - try to get namespace array
                                    await client.get_namespace_array()
                                except Exception as e:
                                    logger.warning(f"Connection to {asset_name} appears dead: {e}")
                                    await self.disconnect_from_asset(asset_name)
                    
            except asyncio.CancelledError:
                logger.info("OPC UA Client shutdown requested")
                
        except Exception as e:
            logger.error(f"Failed to start OPC UA Client: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the OPC UA client and disconnect from all assets"""
        logger.info("Stopping OPC UA Client...")
        self.is_running = False
        
        # Disconnect from all assets
        for asset_name in list(self.clients.keys()):
            await self.disconnect_from_asset(asset_name)
        
        logger.info("OPC UA Client stopped")


class DataChangeHandler:
    """Handler for OPC UA data change notifications"""
    
    def __init__(self, asset: AssetConfiguration, callbacks: List[Callable[[TelemetryPoint], None]]):
        self.asset = asset
        self.callbacks = callbacks
        self.logger = logging.getLogger(f"{__name__}.{asset.asset_name}")
    
    def datachange_notification(self, event: ua.DataChangeNotification):
        """Handle data change notifications"""
        try:
            for item in event.monitored_items:
                node_id = item.ClientHandle
                value = item.Value.Value
                
                # Find tag name by reverse lookup (simplified approach)
                tag_name = self._find_tag_name(node_id)
                if not tag_name:
                    self.logger.warning(f"Unknown node ID: {node_id}")
                    continue
                
                # Create telemetry point
                telemetry_point = TelemetryPoint(
                    timestamp=datetime.utcnow(),
                    enterprise="GlobalCorp",  # Should be from config
                    site=self.asset.metadata.get('site', 'Unknown'),
                    area=self.asset.metadata.get('area', 'Unknown'),
                    line=self.asset.metadata.get('line', 'Unknown'),
                    machine=self.asset.asset_name,
                    tag=tag_name,
                    value=value,
                    unit=None,
                    quality=Quality.GOOD
                )
                
                # Call all callbacks
                for callback in self.callbacks:
                    try:
                        callback(telemetry_point)
                    except Exception as e:
                        self.logger.error(f"Error in data callback: {e}")
                
                self.logger.debug(f"Received data: {tag_name} = {value}")
                
        except Exception as e:
            self.logger.error(f"Error in data change notification: {e}")
    
    def _find_tag_name(self, node_id) -> Optional[str]:
        """Find tag name by node ID (simplified implementation)"""
        # In a real implementation, this would maintain a reverse mapping
        # For now, we'll use a simple approach
        for tag_name, tag_node_id in self.asset.node_mapping.items():
            if str(node_id) in str(tag_node_id):
                return tag_name
        return None
