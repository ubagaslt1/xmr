#!/bin/bash
set -e

echo "=========================================="
echo "Monero Trusted Network - Starting..."
echo "=========================================="

# Create necessary directories
mkdir -p /data/{seeds,logs,db,blockchain,tor}

# Initialize database
if [ ! -f /data/db/network.db ]; then
    echo "Initializing database..."
    sqlite3 /data/db/network.db < /app/init_db.sql
fi

# Generate trusted seeds if needed
if [ ! -f /data/seeds/trusted_seeds.json ]; then
    echo "Generating 1000 trusted seeds..."
    python3 /app/generate_trusted_seeds.py \
        --count 1000 \
        --output /data/seeds/trusted_seeds.json \
        --db /data/db/network.db
fi

# Start services
echo "Starting services..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
