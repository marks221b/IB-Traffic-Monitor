import time
import re
import subprocess
import logging
import argparse
import sys

logging.basicConfig(level=logging.INFO)

class DummyHostManager:
    def __init__(self):
        self.host_uid = "local_host"
        self.node_name = "localhost"

def get_available_interfaces():
    """Get all available IB interfaces in the system"""
    try:
        ibdev_output = subprocess.check_output("ibdev2netdev -v", shell=True, text=True)
        ib_dev_map = {}
        for line in ibdev_output.strip().split('\n'):
            if 'mlx5_' in line and '==>' in line:
                match = re.search(r'(mlx5_\d+).*==> ((?:ib|ibp)\w+)', line)
                if match:
                    nic_name, ipoib_ifname = match.groups()
                    ib_dev_map[ipoib_ifname.strip()] = nic_name
        return ib_dev_map
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get IB device mapping: {e}")
        return {}

def collect_ib_interface_counters(host_manager, interfaces=None):
    """Collect IB interface counter information, optionally for specified interfaces"""
    try:
        ib_interfaces = []
        current_time = time.time()

        if not hasattr(collect_ib_interface_counters, '_prev_stats'):
            collect_ib_interface_counters._prev_stats = {}
            collect_ib_interface_counters._prev_time = current_time

        try:
            ibdev_output = subprocess.check_output("ibdev2netdev -v", shell=True, text=True)
            ib_dev_map = {}
            for line in ibdev_output.strip().split('\n'):
                if 'mlx5_' in line and '==>' in line:
                    match = re.search(r'(mlx5_\d+).*==> ((?:ib|ibp)\w+)', line)
                    if match:
                        nic_name, ipoib_ifname = match.groups()
                        ib_dev_map[nic_name] = ipoib_ifname.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to get IB device mapping: {e}")
            return []

        # If interfaces are specified, only process those
        if interfaces:
            filtered_dev_map = {}
            for device, ipoib_ifname in ib_dev_map.items():
                if ipoib_ifname in interfaces:
                    filtered_dev_map[device] = ipoib_ifname
            
            # Check if all requested interfaces were found
            found_interfaces = set(filtered_dev_map.values())
            missing_interfaces = set(interfaces) - found_interfaces
            if missing_interfaces:
                logging.error(f"The following interfaces were not found: {', '.join(missing_interfaces)}")
                if not filtered_dev_map:  # If no interfaces were found, return empty list
                    return []
            
            ib_dev_map = filtered_dev_map

        for device, ipoib_ifname in ib_dev_map.items():
            try:
                with open(f'/sys/class/infiniband/{device}/node_guid') as f:
                    guid = f.read().strip().replace(':', '')

                process = subprocess.Popen(f'ethtool -S {ipoib_ifname}', shell=True,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, error = process.communicate()
                if process.returncode != 0:
                    continue

                curr_stats = {}
                for line in output.decode().split('\n'):
                    if 'vport_rdma_unicast_bytes' in line:
                        key, val = line.strip().split(':')
                        key = key.strip()
                        val = int(val.strip().replace(',', ''))
                        curr_stats[key] = val

                rx_rate = tx_rate = 0
                device_key = f"{host_manager.host_uid}:{device}"

                if device_key in collect_ib_interface_counters._prev_stats:
                    prev_stats = collect_ib_interface_counters._prev_stats[device_key]
                    time_delta = current_time - collect_ib_interface_counters._prev_time
                    if time_delta > 0:
                        rx_bytes = curr_stats.get('rx_vport_rdma_unicast_bytes', 0) - \
                                   prev_stats.get('rx_vport_rdma_unicast_bytes', 0)
                        tx_bytes = curr_stats.get('tx_vport_rdma_unicast_bytes', 0) - \
                                   prev_stats.get('tx_vport_rdma_unicast_bytes', 0)
                        if rx_bytes < 0:
                            rx_bytes = curr_stats.get('rx_vport_rdma_unicast_bytes', 0)
                        if tx_bytes < 0:
                            tx_bytes = curr_stats.get('tx_vport_rdma_unicast_bytes', 0)
                        rx_rate = (rx_bytes * 8) / (time_delta * 1e9)
                        tx_rate = (tx_bytes * 8) / (time_delta * 1e9)

                collect_ib_interface_counters._prev_stats[device_key] = curr_stats

                interface_data = {
                    'guid': guid,
                    'nic_name': device,
                    'ipoib_ifname': ipoib_ifname,
                    'tx_rate_gbps': round(tx_rate, 3),
                    'rx_rate_gbps': round(rx_rate, 3)
                }
                ib_interfaces.append(interface_data)

            except Exception as e:
                logging.error(f"Error processing device {device}: {str(e)}")
                continue

        collect_ib_interface_counters._prev_time = current_time
        return ib_interfaces

    except Exception as e:
        logging.error(f"Error collecting IB interface counter information: {str(e)}")
        return []

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Monitor InfiniBand interface traffic')
    parser.add_argument('-i', '--interfaces', help='Interfaces to monitor, comma-separated (e.g., ibs1,ibs2)')
    parser.add_argument('-l', '--list', action='store_true', help='List all available IB interfaces')
    parser.add_argument('-t', '--time', type=float, default=2.0, help='Refresh interval (seconds), default is 2 seconds')
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()
    
    # If requested to list all interfaces
    if args.list:
        interfaces = get_available_interfaces()
        if interfaces:
            print("Available IB interfaces:")
            for iface, dev in interfaces.items():
                print(f"  {iface} ({dev})")
        else:
            print("No available IB interfaces found")
        return
    
    # Parse interfaces to monitor
    selected_interfaces = None
    if args.interfaces:
        selected_interfaces = [iface.strip() for iface in args.interfaces.split(',')]
    
    host_manager = DummyHostManager()
    
    try:
        print("Press Ctrl+C to exit monitoring")
        while True:
            ib_stats = collect_ib_interface_counters(host_manager, selected_interfaces)
            
            if not ib_stats:
                if selected_interfaces:
                    print(f"Specified interfaces not found: {', '.join(selected_interfaces)}")
                    return
                else:
                    print("No IB interfaces found")
                    return
            
            # Clear screen (Linux/macOS)
            print("\033c", end="")
            
            print(f"========== IB Interface Traffic Statistics (Update: {args.time}s) ==========")
            print(f"{'Interface':12} {'Device':10} {'TX (Gbps)':12} {'RX (Gbps)':12}")
            print("-" * 50)
            
            for iface in ib_stats:
                print(f"{iface['ipoib_ifname']:12} {iface['nic_name']:10} "
                      f"{iface['tx_rate_gbps']:12.3f} {iface['rx_rate_gbps']:12.3f}")
            
            print("=" * 50)
            time.sleep(args.time)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        logging.error(f"Runtime error: {str(e)}")

if __name__ == "__main__":
    main() 
