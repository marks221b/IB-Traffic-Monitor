# IB-Traffic-Monitor
infiniband monitor

Overview
IB-Traffic-Monitor is a Python-based utility designed for system administrators and HPC engineers who need to monitor InfiniBand network traffic. It provides real-time statistics on transmit and receive rates for IB interfaces, helping with performance analysis and troubleshooting.

# Requirements

Python 3

InfiniBand hardware with MLNX-OFED drivers installed

ibdev2netdev and ethtool utilities

# Installation
git clone https://github.com/marks221b/ib-traffic-monitor.git
cd ib-traffic-monitor
chmod +x ib_traffic_monitor.py

# Usage
Basic usage - monitor all interfaces
python3 ib_traffic_monitor.py

python3 ib_traffic_monitor.py -l

python3 ib_traffic_monitor.py -i ibs1,ibs2

python3 ib_traffic_monitor.py -t 5

python3 ib_traffic_monitor.py -i ibs1 -t 1


```markdown
## Example Output

| Interface | Device | TX (Gbps) | RX (Gbps) |
|-----------|--------|-----------|-----------|
| ibs1      | mlx5_0 | 1.234     | 2.345     |
| ibs2      | mlx5_1 | 0.123     | 0.456     |
```
