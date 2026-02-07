"""Security-hardened OPC UA Simulation Server"""

import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, List
import yaml
from asyncua import Server, ua
from asyncua.common.methods import uamethod

from cert_utils import generate_self_signed_certificate, create_trust_store

# Add parent directory to path for common models
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import BridgeConfiguration


class OPCUASimulationServer:
    """Security-hardened OPC UA server with dynamic node creation and simulation"""
    
    def __init__(self, config_path: str = "../../use_case_config.yaml"):
        self.config_path = config_path
        self.server = None
        self.config = None
        self.node_variables: Dict[str, Any] = {}
        self.simulation_tasks: List[asyncio.Task] = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def load_config(self) -> BridgeConfiguration:
        """Load configuration from YAML file"""
        try:
            config_file = Path(__file__).parent / self.config_path
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            self.config = BridgeConfiguration(**config_data)
            self.logger.info(f"Loaded configuration for enterprise: {self.config.enterprise_name}")
            return self.config
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    async def setup_security(self) -> Server:
        """Setup OPC UA server with X.509 certificate security"""
        self.logger.info("Setting up OPC UA server with security...")
        
        # Generate certificates
        cert_file, key_file = generate_self_signed_certificate(
            cert_dir="../../opcua-server-sim/certs",
            server_name="OPCUA-Simulation-Server"
        )
        
        # Create trust store
        trust_store = create_trust_store("../../opcua-server-sim/certs")
        
        # Setup server
        server = Server()
        server.set_server_name("OPCUA Simulation Server")
        server.set_endpoint("opc.tcp://0.0.0.0:4840/")
        
        # Setup security policies
        server.set_security_policy([
            ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            ua.SecurityPolicyType.Basic256Sha256_Sign,
        ])
        
        # Load certificate and private key
        await server.load_certificate(cert_file)
        await server.load_private_key(key_file)
        
        # Setup user identity tokens (X.509 certificates)
        server.set_security_IDs([ua.UserNamePasswordUserPolicy(), ua.X509UserPolicy()])
        
        self.logger.info("Security setup completed")
        return server
    
    async def create_dynamic_nodes(self):
        """Create OPC UA nodes dynamically from configuration"""
        self.logger.info("Creating dynamic nodes from configuration...")
        
        # Get the default namespace
        uri = "http://globalcorp.com/opcua/simulation"
        idx = await self.server.register_namespace(uri)
        
        # Create objects folder for simulation
        objects = self.server.get_objects_node()
        
        for site in self.config.sites:
            for asset in site.assets:
                # Create asset object
                asset_node = await objects.add_object(idx, asset.asset_name)
                await asset_node.set_attribute(ua.AttributeIds.Description, asset.description or "")
                
                # Create variables for each mapped tag
                for tag_name, node_id in asset.node_mapping.items():
                    # Determine variable type based on tag name
                    variant_type = self._get_variant_type(tag_name)
                    
                    # Create variable
                    var_node = await asset_node.add_variable(idx, tag_name, 0.0, variant_type)
                    await var_node.set_attribute(ua.AttributeIds.Description, f"Simulated {tag_name}")
                    
                    # Make variable writable for some tags
                    if tag_name in ["MachineState"]:
                        await var_node.set_writable()
                    
                    # Store reference for simulation
                    self.node_variables[f"{asset.asset_name}.{tag_name}"] = {
                        'node': var_node,
                        'type': variant_type,
                        'asset': asset,
                        'tag': tag_name
                    }
                    
                    self.logger.info(f"Created variable: {asset.asset_name}.{tag_name}")
        
        self.logger.info(f"Created {len(self.node_variables)} dynamic variables")
    
    def _get_variant_type(self, tag_name: str) -> ua.VariantType:
        """Determine OPC UA variant type based on tag name"""
        tag_lower = tag_name.lower()
        
        if any(keyword in tag_lower for keyword in ['speed', 'vibration', 'temperature', 'pressure', 'rate']):
            return ua.VariantType.Double
        elif any(keyword in tag_lower for keyword in ['count', 'cycle']):
            return ua.VariantType.UInt32
        elif 'state' in tag_lower:
            return ua.VariantType.String
        elif 'status' in tag_lower:
            return ua.VariantType.String
        else:
            return ua.VariantType.Double
    
    async def simulate_data(self):
        """Main simulation loop for realistic data generation"""
        self.logger.info("Starting data simulation...")
        
        while True:
            try:
                current_time = time.time()
                
                for var_key, var_info in self.node_variables.items():
                    value = await self._generate_simulated_value(var_key, var_info, current_time)
                    await var_info['node'].write_value(value)
                
                await asyncio.sleep(1.0)  # Update every second
                
            except Exception as e:
                self.logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _generate_simulated_value(self, var_key: str, var_info: Dict, current_time: float) -> Any:
        """Generate realistic simulated values for different tag types"""
        tag_name = var_info['tag']
        asset = var_info['asset']
        
        # Motor speed simulation (RPM with realistic variations)
        if 'MotorSpeed' in tag_name:
            base_speed = 1800.0
            variation = random.uniform(-50, 50)
            noise = random.uniform(-5, 5)
            return base_speed + variation + noise
        
        # Vibration simulation (mm/s with occasional spikes)
        elif 'Vibration' in tag_name:
            base_vibration = 2.0
            if random.random() < 0.05:  # 5% chance of spike
                return random.uniform(8.0, 12.0)
            return base_vibration + random.uniform(-0.5, 0.5)
        
        # Temperature simulation (Celsius with daily cycle)
        elif 'Temperature' in tag_name:
            base_temp = 45.0
            daily_cycle = 5.0 * (0.5 - 0.5 * (current_time % 86400) / 43200)  # Sinusoidal daily variation
            return base_temp + daily_cycle + random.uniform(-2, 2)
        
        # Pressure simulation (Bar)
        elif 'Pressure' in tag_name:
            base_pressure = 6.0
            return base_pressure + random.uniform(-0.3, 0.3)
        
        # Cycle count simulation (incrementing counter)
        elif 'CycleCount' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                increment = random.randint(1, 3)
                return int(current_value) + increment
            return 1
        
        # Machine state simulation
        elif 'MachineState' in tag_name:
            states = ["Running", "Idle", "Starting", "Stopping", "Maintenance"]
            weights = [0.7, 0.15, 0.05, 0.05, 0.05]
            return random.choices(states, weights=weights)[0]
        
        # Production rate simulation
        elif 'ProductionRate' in tag_name:
            base_rate = 200.0  # units per hour
            efficiency = random.uniform(0.85, 1.05)
            return base_rate * efficiency
        
        # Power consumption simulation (kW)
        elif 'PowerConsumption' in tag_name:
            base_power = 15.0
            load_factor = random.uniform(0.8, 1.2)
            return base_power * load_factor
        
        # Quality status simulation
        elif 'QualityStatus' in tag_name:
            statuses = ["Good", "Warning", "Error"]
            weights = [0.92, 0.07, 0.01]
            return random.choices(statuses, weights=weights)[0]
        
        # Conveyor speed simulation
        elif 'ConveyorSpeed' in tag_name:
            base_speed = 1.5  # m/s
            return base_speed + random.uniform(-0.1, 0.1)
        
        # Package count simulation
        elif 'PackageCount' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                return int(current_value) + random.randint(1, 2)
            return 1
        
        # Default simulation
        else:
            return random.uniform(0, 100)
    
    async def start(self):
        """Start the OPC UA server"""
        try:
            # Load configuration
            await self.load_config()
            
            # Setup security
            self.server = await self.setup_security()
            
            # Start server
            await self.server.start()
            self.logger.info("OPC UA Server started successfully on opc.tcp://0.0.0.0:4840/")
            
            # Create dynamic nodes
            await self.create_dynamic_nodes()
            
            # Start simulation
            simulation_task = asyncio.create_task(self.simulate_data())
            self.simulation_tasks.append(simulation_task)
            
            self.logger.info("Server fully operational with simulation running")
            
            # Keep server running
            try:
                while True:
                    await asyncio.sleep(3600)  # Check every hour
            except asyncio.CancelledError:
                self.logger.info("Server shutdown requested")
                
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the OPC UA server"""
        self.logger.info("Stopping OPC UA server...")
        
        # Cancel simulation tasks
        for task in self.simulation_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Stop server
        if self.server:
            await self.server.stop()
        
        self.logger.info("Server stopped")


async def main():
    """Main entry point"""
    server = OPCUASimulationServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
