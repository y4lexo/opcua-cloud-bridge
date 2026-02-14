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
        
        if any(keyword in tag_lower for keyword in ['voltage', 'current', 'power', 'energy', 'frequency', 'efficiency', 'irradiance', 'soc', 'thd']):
            return ua.VariantType.Double
        elif any(keyword in tag_lower for keyword in ['count', 'cycle']):
            return ua.VariantType.UInt32
        elif any(keyword in tag_lower for keyword in ['state', 'status']):
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
        """Generate realistic simulated values for energy equipment"""
        tag_name = var_info['tag']
        asset = var_info['asset']
        
        # Solar inverter voltage simulation (3-phase, 400V nominal)
        if 'Voltage_L' in tag_name:
            nominal_voltage = 400.0 / 1.732  # Phase voltage for 400V 3-phase
            variation = random.uniform(-5, 5)  # ±5% variation
            harmonic_distortion = random.uniform(-2, 2)
            return nominal_voltage + variation + harmonic_distortion
        
        # Solar inverter current simulation (proportional to irradiance)
        elif 'Current_L' in tag_name:
            base_current = 720.0  # Approximate current for 500kW at 400V
            irradiance_factor = 0.3 + 0.7 * (0.5 + 0.5 * (current_time % 86400) / 43200)  # Day/night cycle
            variation = random.uniform(-10, 10)
            return max(0, base_current * irradiance_factor + variation)
        
        # Solar active power simulation (kW, follows irradiance)
        elif 'Power_Active' in tag_name:
            base_power = 500.0  # 500kW inverter
            # Realistic daily solar generation curve
            hour_of_day = (current_time % 86400) / 3600
            if 6 <= hour_of_day <= 18:  # Daylight hours
                solar_factor = 0.9 * (1 - ((hour_of_day - 12) / 6) ** 2)  # Parabolic curve
            else:
                solar_factor = 0.0
            cloud_cover = random.uniform(0.8, 1.0)  # Random cloud cover
            return base_power * solar_factor * cloud_cover
        
        # Solar reactive power simulation (kVAR)
        elif 'Power_Reactive' in tag_name:
            active_power = await self._get_related_value(var_key, 'Power_Active', current_time)
            power_factor = random.uniform(0.95, 0.99)
            return active_power * (1 - power_factor) / power_factor
        
        # Solar energy total simulation (kWh, cumulative)
        elif 'Energy_Total' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                power_kw = await self._get_related_value(var_key, 'Power_Active', current_time)
                increment = power_kw / 3600  # kWh per second
                return current_value + increment
            return 0.0
        
        # Grid frequency simulation (Hz)
        elif 'Frequency' in tag_name:
            nominal_freq = 50.0
            grid_stability = random.uniform(-0.1, 0.1)
            return nominal_freq + grid_stability
        
        # Solar inverter efficiency simulation (%)
        elif 'Efficiency' in tag_name:
            base_efficiency = 96.0
            load_factor = random.uniform(0.8, 1.0)
            temperature_derating = random.uniform(-2, 0)
            return base_efficiency * load_factor + temperature_derating
        
        # Solar irradiance simulation (W/m²)
        elif 'Irradiance' in tag_name:
            hour_of_day = (current_time % 86400) / 3600
            if 6 <= hour_of_day <= 18:
                base_irradiance = 800 * (1 - ((hour_of_day - 12) / 6) ** 2)
                cloud_factor = random.uniform(0.7, 1.0)
                return base_irradiance * cloud_factor
            else:
                return 0.0
        
        # Battery voltage simulation (V)
        elif 'Voltage' in tag_name and 'Battery' in asset.asset_name:
            base_voltage = 800.0  # 800V battery system
            soc_factor = random.uniform(0.95, 1.05)
            return base_voltage * soc_factor
        
        # Battery current simulation (A, positive for charge, negative for discharge)
        elif 'Current' in tag_name and 'Battery' in asset.asset_name:
            if 'Power_Charge' in asset.node_mapping:
                charge_power = await self._get_related_value(var_key, 'Power_Charge', current_time)
                discharge_power = await self._get_related_value(var_key, 'Power_Discharge', current_time)
                net_power = discharge_power - charge_power
                return net_power / 800.0  # Current = Power/Voltage
            return random.uniform(-100, 100)
        
        # Battery charge power simulation (kW)
        elif 'Power_Charge' in tag_name:
            base_charge = 200.0
            solar_excess = random.uniform(0, 1)  # Solar excess available
            return base_charge * solar_excess
        
        # Battery discharge power simulation (kW)
        elif 'Power_Discharge' in tag_name:
            base_discharge = 250.0
            demand_factor = random.uniform(0, 1)  # Grid demand
            return base_discharge * demand_factor
        
        # Battery State of Charge simulation (%)
        elif 'SoC' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                charge_power = await self._get_related_value(var_key, 'Power_Charge', current_time)
                discharge_power = await self._get_related_value(var_key, 'Power_Discharge', current_time)
                net_power = charge_power - discharge_power
                soc_change = (net_power / 1000.0) / 3600  # SoC change per second
                new_soc = current_value + soc_change
                return max(10, min(90, new_soc))  # Limit between 10% and 90%
            return 50.0
        
        # Battery temperature simulation (°C)
        elif 'Temperature_Cell' in tag_name:
            base_temp = 25.0
            current = await self._get_related_value(var_key, 'Current', current_time)
            heating = abs(current) * 0.02  # Temperature rise due to current
            ambient = random.uniform(15, 30)
            return base_temp + heating + ambient - 20
        
        # Ambient temperature simulation (°C)
        elif 'Temperature_Ambient' in tag_name:
            hour_of_day = (current_time % 86400) / 3600
            daily_cycle = 10 * (0.5 - 0.5 * (hour_of_day - 14) / 10)
            base_temp = 20.0
            return base_temp + daily_cycle + random.uniform(-2, 2)
        
        # Battery health index simulation (%)
        elif 'Health_Index' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                degradation = 0.0001  # Very slow degradation
                return max(80, current_value - degradation)
            return 98.0
        
        # Smart meter power import simulation (kW)
        elif 'Power_Import' in tag_name:
            base_load = 300.0  # 300kW commercial load
            time_factor = 1.0 + 0.3 * (0.5 - 0.5 * ((current_time % 86400) / 3600 - 12) / 12)
            return base_load * time_factor + random.uniform(-20, 20)
        
        # Smart meter power export simulation (kW)
        elif 'Power_Export' in tag_name:
            solar_generation = 400.0 * (0.5 + 0.5 * (current_time % 86400) / 43200)
            building_load = await self._get_related_value(var_key, 'Power_Import', current_time)
            net_export = max(0, solar_generation - building_load)
            return net_export
        
        # Energy cumulative counters
        elif any(keyword in tag_name for keyword in ['Energy_Total', 'Energy_Import_Total', 'Energy_Export_Total', 'Energy_Charged', 'Energy_Discharged']):
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                # Find corresponding power value
                power_tag = tag_name.replace('Energy_Total', 'Power_Total').replace('Energy_Import_Total', 'Power_Import').replace('Energy_Export_Total', 'Power_Export').replace('Energy_Charged', 'Power_Charge').replace('Energy_Discharged', 'Power_Discharge')
                power_value = await self._get_related_value(var_key, power_tag, current_time)
                increment = abs(power_value) / 3600 if power_value else 0
                return current_value + increment
            return 0.0
        
        # Power factor simulation
        elif 'Power_Factor' in tag_name:
            return random.uniform(0.95, 0.99)
        
        # Total harmonic distortion simulation (%)
        elif 'THD' in tag_name:
            return random.uniform(2, 5)  # 2-5% THD is typical
        
        # Load panel power simulation (kW)
        elif 'Power_Total' in tag_name and 'Load' in asset.asset_name:
            base_load = 250.0
            time_factor = 1.0 + 0.4 * (0.5 - 0.5 * ((current_time % 86400) / 3600 - 14) / 10)
            return base_load * time_factor + random.uniform(-15, 15)
        
        # Equipment state simulation
        elif any(keyword in tag_name for keyword in ['Inverter_State', 'Battery_State', 'Meter_State', 'Panel_State']):
            states = ["Running", "Standby", "Fault", "Maintenance"]
            weights = [0.85, 0.10, 0.03, 0.02]
            return random.choices(states, weights=weights)[0]
        
        # Cycle count simulation (incrementing counter)
        elif 'Cycle_Count' in tag_name:
            current_value = await var_info['node'].read_value()
            if isinstance(current_value, (int, float)):
                increment = random.randint(0, 1)  # Battery cycles are slow
                return int(current_value) + increment
            return 0
        
        # Temperature simulation (general)
        elif 'Temperature' in tag_name and 'Battery' not in asset.asset_name:
            base_temp = 35.0
            daily_cycle = 15 * (0.5 - 0.5 * (current_time % 86400) / 43200)
            return base_temp + daily_cycle + random.uniform(-3, 3)
        
        # Default simulation
        else:
            return random.uniform(0, 100)
    
    async def _get_related_value(self, var_key: str, related_tag: str, current_time: float) -> float:
        """Get value from a related tag for simulation consistency"""
        # Find the related variable
        asset_name = var_key.split('.')[0]
        related_key = f"{asset_name}.{related_tag}"
        
        if related_key in self.node_variables:
            related_var = self.node_variables[related_key]
            try:
                value = await related_var['node'].read_value()
                return float(value) if isinstance(value, (int, float)) else 0.0
            except:
                pass
        
        # Return a default value if related tag not found
        return 0.0
    
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
