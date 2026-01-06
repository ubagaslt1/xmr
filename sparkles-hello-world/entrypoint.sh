#!/bin/bash
set -e

echo "=========================================="
echo "Monero Trusted Network - 1000 Seeds Only"
echo "=========================================="
echo ""
echo "This network ONLY trusts our 1000 generated seeds."
echo "All other Monero nodes are marked as UNTRUSTED."
echo ""

# Create directories
mkdir -p /data/{seeds,trusted,untrusted,logs,db,blockchain,tor/{trusted,untrusted}}

# Initialize database
if [ ! -f /data/db/network.db ]; then
    echo "Initializing trusted network database..."
    sqlite3 /data/db/network.db < /app/init_db.sql
fi

# Generate trusted seeds if they don't exist
if [ ! -f /data/seeds/trusted_seeds.json ]; then
    echo "Generating 1000 trusted Tor onion seeds..."
    echo "These will be the ONLY trusted nodes in the network."
    
    python3 /generate_trusted_seeds.py \
        --count 1000 \
        --output /data/seeds/trusted_seeds.json \
        --db /data/db/network.db
    
    echo "✓ Generated 1000 trusted seeds"
    echo "✓ Stored in database"
fi

# Load existing untrusted nodes from Monero network
echo "Loading existing Monero nodes to mark as untrusted..."
python3 /block_untrusted.py --init

# Create network configuration
echo "Creating exclusive network configuration..."
python3 /create_network.py \
    --trusted /data/seeds/trusted_seeds.json \
    --output /data/trusted/monerod.conf \
    --blockchain-dir /blockchain

# Start Tor for trusted seeds
echo "Starting Tor services for trusted seeds..."
for i in {1..50}; do  # Start first 50 seeds initially
    if [ -f /data/tor/trusted/torrc.$i ]; then
        tor -f /data/tor/trusted/torrc.$i --RunAsDaemon 1
    fi
done

# Setup firewall to block untrusted connections
echo "Setting up network firewall..."
bash /firewall.sh --setup

# Start monitoring
echo "Starting network monitor..."
python3 /monitor_network.py --daemon &

# Start enforcement daemon
echo "Starting trust enforcement daemon..."
python3 /enforce_trust.py --daemon &

# Start web interface
echo "Starting web interface..."
nginx
python3 /app/web/app.py &

# Start Monero node with trusted-only config
echo "Starting Monero node (trusted network only)..."
monerod --config-file /data/trusted/monerod.conf --detach

echo ""
echo "=========================================="
echo "Trusted Network Active"
echo "=========================================="
echo ""
echo "✓ 1000 trusted seeds generated"
echo "✓ All other nodes marked as untrusted"
echo "✓ Firewall blocking untrusted connections"
echo "✓ Exclusive network configuration applied"
echo ""
echo "Network Status:"
echo "  Web Interface: http://your-umbrel.local:8080"
echo "  Trusted Seeds: 1000"
echo "  Blocked Nodes: ALL external nodes"
echo ""
echo "This node will ONLY connect to our 1000 trusted seeds."
echo "All other Monero nodes are explicitly untrusted."

# Keep container running
tail -f /data/logs/monerod.log /data/logs/network.log
