"""Configuration management with environment variable overrides"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Add parent directory to path for common models
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import BridgeConfiguration

logger = logging.getLogger(__name__)


class ConfigManager:
    """Configuration manager with environment variable override support"""
    
    def __init__(self, config_path: str = "../../use_case_config.yaml"):
        self.config_path = config_path
        self.config: Optional[BridgeConfiguration] = None
        
    def load_config(self) -> BridgeConfiguration:
        """Load configuration from YAML file with environment variable overrides"""
        try:
            # Load base configuration
            config_file = Path(__file__).parent / self.config_path
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Apply environment variable overrides
            config_data = self._apply_env_overrides(config_data)
            
            # Create configuration object
            self.config = BridgeConfiguration(**config_data)
            logger.info(f"Configuration loaded: {self.config.enterprise_name}")
            
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration"""
        
        # Override OPC UA server URLs
        opcua_url_override = os.getenv('OPCUA_SERVER_URL')
        if opcua_url_override:
            logger.info(f"Overriding OPC UA server URL: {opcua_url_override}")
            self._override_opcua_urls(config_data, opcua_url_override)
        
        # Override Node IDs
        node_id_overrides = self._parse_node_id_overrides()
        if node_id_overrides:
            logger.info(f"Applying {len(node_id_overrides)} Node ID overrides")
            self._override_node_ids(config_data, node_id_overrides)
        
        # Override security settings
        security_policy = os.getenv('OPCUA_SECURITY_POLICY')
        if security_policy:
            logger.info(f"Overriding security policy: {security_policy}")
            self._override_security_policy(config_data, security_policy)
        
        # Override connection settings
        connection_timeout = os.getenv('OPCUA_CONNECTION_TIMEOUT')
        if connection_timeout:
            try:
                timeout = float(connection_timeout)
                config_data.setdefault('global_settings', {})['connection_timeout'] = timeout
                logger.info(f"Overriding connection timeout: {timeout}s")
            except ValueError:
                logger.warning(f"Invalid connection timeout value: {connection_timeout}")
        
        return config_data
    
    def _override_opcua_urls(self, config_data: Dict[str, Any], new_url: str):
        """Override OPC UA server URLs for all assets"""
        if 'sites' in config_data:
            for site in config_data['sites']:
                if 'assets' in site:
                    for asset in site['assets']:
                        asset['opcua_endpoint'] = new_url
    
    def _parse_node_id_overrides(self) -> Dict[str, str]:
        """Parse Node ID overrides from environment variables"""
        overrides = {}
        
        # Look for environment variables in format: NODE_ID_<ASSET>_<TAG>=<node_id>
        prefix = 'NODE_ID_'
        for env_var, value in os.environ.items():
            if env_var.startswith(prefix):
                # Parse asset and tag from variable name
                parts = env_var[len(prefix):].split('_', 1)
                if len(parts) == 2:
                    asset_name = parts[0]
                    tag_name = parts[1]
                    key = f"{asset_name}.{tag_name}"
                    overrides[key] = value
                    logger.debug(f"Node ID override: {key} -> {value}")
        
        return overrides
    
    def _override_node_ids(self, config_data: Dict[str, Any], overrides: Dict[str, str]):
        """Override Node IDs in configuration"""
        if 'sites' in config_data:
            for site in config_data['sites']:
                if 'assets' in site:
                    for asset in site['assets']:
                        asset_name = asset.get('asset_name', '')
                        if 'node_mapping' in asset:
                            for tag_name in list(asset['node_mapping'].keys()):
                                key = f"{asset_name}.{tag_name}"
                                if key in overrides:
                                    asset['node_mapping'][tag_name] = overrides[key]
                                    logger.debug(f"Updated Node ID for {key}: {overrides[key]}")
    
    def _override_security_policy(self, config_data: Dict[str, Any], policy: str):
        """Override security policy for all assets"""
        if 'sites' in config_data:
            for site in config_data['sites']:
                if 'assets' in site:
                    for asset in site['assets']:
                        asset.setdefault('security_settings', {})['security_policy'] = policy
    
    def get_asset_config(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific asset"""
        if not self.config:
            return None
        
        for site in self.config.sites:
            for asset in site.assets:
                if asset.asset_name == asset_name:
                    return {
                        'asset_name': asset.asset_name,
                        'opcua_endpoint': asset.opcua_endpoint,
                        'node_mapping': asset.node_mapping,
                        'security_settings': getattr(asset, 'security_settings', {}),
                        'metadata': asset.metadata
                    }
        return None
    
    def get_connection_settings(self) -> Dict[str, Any]:
        """Get global connection settings"""
        if not self.config:
            return {}
        
        return {
            'connection_timeout': self.config.global_settings.get('connection_timeout', 10.0),
            'retry_attempts': self.config.global_settings.get('retry_attempts', 3),
            'retry_delay': self.config.global_settings.get('retry_delay', 5.0),
            'security_policy': self.config.global_settings.get('security_policy', 'Basic256Sha256')
        }


# Global configuration manager instance
config_manager = ConfigManager()


def load_config() -> BridgeConfiguration:
    """Load configuration with environment variable overrides"""
    return config_manager.load_config()


def get_asset_config(asset_name: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific asset"""
    return config_manager.get_asset_config(asset_name)


def get_connection_settings() -> Dict[str, Any]:
    """Get global connection settings"""
    return config_manager.get_connection_settings()
