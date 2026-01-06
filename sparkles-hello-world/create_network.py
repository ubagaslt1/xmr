#!/usr/bin/env python3
import json
import time

print("Creating network configuration...")
config = """p2p-bind-ip=0.0.0.0
p2p-bind-port=18080
rpc-bind-ip=0.0.0.0
rpc-bind-port=18089
data-dir=/blockchain
log-file=/data/logs/monerod.log"""

with open('/data/monerod.conf', 'w') as f:
    f.write(config)

print("✓ Created monerod.conf")
