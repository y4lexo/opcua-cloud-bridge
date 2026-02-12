"""OPC UA Node Discovery Utility

This script connects to an OPC UA server and discovers the address space,
printing available nodes, their properties, and data types. Useful for
finding the correct Node IDs on physical PLCs.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from asyncua import Client, ua
from datetime import datetime

# Add parent directory to path for common models
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OPCUANodeDiscovery:
    """OPC UA Node Discovery utility"""
    
    def __init__(self, endpoint: str, security_policy: str = "None"):
        self.endpoint = endpoint
        self.security_policy = security_policy
        self.client = None
        self.discovered_nodes = {}
        self.max_depth = 3  # Maximum depth for recursive discovery
        
    async def connect(self) -> bool:
        """Connect to OPC UA server with security negotiation"""
        try:
            logger.info(f"Connecting to {self.endpoint}")
            
            # Create client
            self.client = Client(url=self.endpoint)
            
            # Setup security
            if self.security_policy == "None":
                self.client.set_security_string("None")
                logger.info("Using no security")
            else:
                # For secure connections, you would need certificates
                logger.warning(f"Security policy {self.security_policy} not fully implemented in discovery tool")
                self.client.set_security_string("None")
            
            # Connect
            await self.client.connect()
            logger.info("Successfully connected to OPC UA server")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def discover_endpoints(self):
        """Discover available endpoints and security policies"""
        try:
            logger.info("Discovering endpoints...")
            
            # Create temporary client with no security to get endpoints
            temp_client = Client(url=self.endpoint)
            temp_client.set_security_string("None")
            await temp_client.connect()
            
            endpoints = await temp_client.get_endpoints()
            await temp_client.disconnect()
            
            logger.info(f"Found {len(endpoints)} endpoints:")
            for i, endpoint in enumerate(endpoints):
                logger.info(f"  Endpoint {i+1}:")
                logger.info(f"    URL: {endpoint.EndpointUrl}")
                logger.info(f"    Security Mode: {endpoint.SecurityMode}")
                if hasattr(endpoint, 'SecurityPolicyUri'):
                    logger.info(f"    Security Policy: {endpoint.SecurityPolicyUri}")
                logger.info(f"    Transport Profile: {endpoint.TransportProfileUri}")
                logger.info("")
            
        except Exception as e:
            logger.error(f"Failed to discover endpoints: {e}")
    
    async def discover_namespaces(self):
        """Discover available namespaces"""
        try:
            logger.info("Discovering namespaces...")
            namespaces = await self.client.get_namespace_array()
            
            logger.info(f"Found {len(namespaces)} namespaces:")
            for i, ns in enumerate(namespaces):
                logger.info(f"  ns={i}: {ns}")
            
            return namespaces
            
        except Exception as e:
            logger.error(f"Failed to discover namespaces: {e}")
            return []
    
    async def browse_node(self, node_id: str, depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
        """Recursively browse a node and its children"""
        if depth > max_depth:
            return {}
        
        try:
            node = await self.client.get_node(node_id)
            
            # Get node information
            node_info = {
                'node_id': str(node_id),
                'browse_name': await node.read_browse_name(),
                'display_name': await node.read_display_name(),
                'node_class': await node.read_node_class(),
                'data_type': None,
                'children': []
            }
            
            # Get data type for variables
            if node_info['node_class'] == ua.NodeClass.Variable:
                try:
                    data_type_node = await node.read_data_type()
                    node_info['data_type'] = await data_type_node.read_browse_name()
                except:
                    pass
            
            # Print current node
            indent = "  " * depth
            logger.info(f"{indent}• {node_info['browse_name']} ({node_info['node_id']})")
            logger.info(f"{indent}  Class: {node_info['node_class']}")
            if node_info['data_type']:
                logger.info(f"{indent}  Type: {node_info['data_type']}")
            if node_info['display_name']:
                logger.info(f"{indent}  Display: {node_info['display_name']}")
            
            # Browse children
            try:
                children = await node.get_children()
                for child in children:
                    child_info = await self.browse_node(
                        str(child.nodeid), 
                        depth + 1, 
                        max_depth
                    )
                    if child_info:
                        node_info['children'].append(child_info)
            except Exception as e:
                logger.warning(f"{indent}  Failed to browse children: {e}")
            
            return node_info
            
        except Exception as e:
            logger.error(f"Failed to browse node {node_id}: {e}")
            return {}
    
    async def discover_objects_folder(self, max_depth: int = 3):
        """Discover the Objects folder and its contents"""
        try:
            logger.info("Discovering Objects folder...")
            
            # Get Objects folder
            objects = self.client.get_objects_node()
            objects_info = await self.browse_node(str(objects.nodeid), 0, max_depth)
            
            return objects_info
            
        except Exception as e:
            logger.error(f"Failed to discover Objects folder: {e}")
            return {}
    
    async def find_nodes_by_type(self, node_type: str = "Variable") -> List[Dict[str, Any]]:
        """Find all nodes of a specific type"""
        try:
            logger.info(f"Finding all {node_type} nodes...")
            
            found_nodes = []
            
            # Start from Objects folder
            objects = self.client.get_objects_node()
            
            async def search_recursive(node, depth=0):
                if depth > 5:  # Limit search depth
                    return
                
                try:
                    node_class = await node.read_node_class()
                    
                    if node_type.lower() in str(node_class).lower():
                        node_info = {
                            'node_id': str(node.nodeid),
                            'browse_name': await node.read_browse_name(),
                            'display_name': await node.read_display_name(),
                            'node_class': node_class
                        }
                        
                        # Get data type for variables
                        if node_class == ua.NodeClass.Variable:
                            try:
                                data_value = await node.read_value()
                                node_info['current_value'] = data_value
                                node_info['value_type'] = type(data_value).__name__
                            except:
                                pass
                        
                        found_nodes.append(node_info)
                        logger.info(f"  Found: {node_info['browse_name']} ({node_info['node_id']})")
                    
                    # Recursively search children
                    children = await node.get_children()
                    for child in children:
                        await search_recursive(child, depth + 1)
                        
                except Exception as e:
                    logger.debug(f"Error searching node: {e}")
            
            await search_recursive(objects)
            
            logger.info(f"Found {len(found_nodes)} {node_type} nodes")
            return found_nodes
            
        except Exception as e:
            logger.error(f"Failed to find nodes by type: {e}")
            return []
    
    async def monitor_node(self, node_id: str, duration: int = 10):
        """Monitor a specific node for changes"""
        try:
            logger.info(f"Monitoring node {node_id} for {duration} seconds...")
            
            node = await self.client.get_node(node_id)
            
            # Read initial value
            initial_value = await node.read_value()
            logger.info(f"Initial value: {initial_value}")
            
            # Create subscription
            handler = DataChangeHandler()
            subscription = await self.client.create_subscription(1000, handler)
            
            # Subscribe to node
            await subscription.subscribe_data_change(node)
            
            # Monitor for specified duration
            await asyncio.sleep(duration)
            
            # Clean up
            await subscription.delete()
            
            logger.info("Monitoring completed")
            
        except Exception as e:
            logger.error(f"Failed to monitor node: {e}")
    
    async def disconnect(self):
        """Disconnect from OPC UA server"""
        try:
            if self.client:
                await self.client.disconnect()
                logger.info("Disconnected from OPC UA server")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def run_discovery(self, max_depth: int = 3, monitor_node: Optional[str] = None):
        """Run complete discovery process"""
        try:
            # Connect
            if not await self.connect():
                return
            
            # Discover endpoints
            await self.discover_endpoints()
            
            # Discover namespaces
            await self.discover_namespaces()
            
            # Discover Objects folder
            await self.discover_objects_folder(max_depth)
            
            # Find all variables
            await self.find_nodes_by_type("Variable")
            
            # Monitor specific node if requested
            if monitor_node:
                await self.monitor_node(monitor_node)
            
        except KeyboardInterrupt:
            logger.info("Discovery interrupted by user")
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
        finally:
            await self.disconnect()


class DataChangeHandler:
    """Handler for data change notifications during discovery"""
    
    def datachange_notification(self, event):
        """Handle data change notifications"""
        try:
            for item in event.monitored_items:
                logger.info(f"  Value changed: {item.Value.Value} (Quality: {item.Value.StatusCode})")
        except Exception as e:
            logger.error(f"Error in data change notification: {e}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='OPC UA Node Discovery Utility')
    parser.add_argument('endpoint', help='OPC UA endpoint URL (e.g., opc.tcp://localhost:4840/)')
    parser.add_argument('--security-policy', default='None', 
                       help='Security policy (None, Basic256Sha256, etc.)')
    parser.add_argument('--max-depth', type=int, default=3,
                       help='Maximum depth for recursive browsing (default: 3)')
    parser.add_argument('--monitor-node', help='Monitor specific node ID for changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create discovery instance
    discovery = OPCUANodeDiscovery(args.endpoint, args.security_policy)
    
    # Run discovery
    await discovery.run_discovery(args.max_depth, args.monitor_node)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiscovery interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
