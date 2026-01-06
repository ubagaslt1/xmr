#!/usr/bin/env python3
import json
import time
import sqlite3
import secrets
import base64
import hashlib

def generate_seed(seed_id):
    """Generate a simple Tor v3-like address."""
    # Generate random bytes
    random_bytes = secrets.token_bytes(32)
    
    # Create onion-like address
    hash_input = f"monero-seed-{seed_id}-{time.time()}".encode()
    hash_value = hashlib.sha256(hash_input).digest()
    onion_address = base64.b32encode(hash_value[:16]).decode().lower() + ".onion"
    
    return {
        'id': seed_id,
        'onion_address': onion_address,
        'port': 18080 + (seed_id % 100),
        'trust_level': 'platinum' if seed_id <= 100 else 'gold' if seed_id <= 300 else 'silver' if seed_id <= 600 else 'bronze',
        'generated_at': time.time()
    }

def main():
    print("Generating 1000 trusted seeds...")
    
    seeds = []
    for i in range(1, 1001):
        seed = generate_seed(i)
        seeds.append(seed)
        if i % 100 == 0:
            print(f"Generated {i} seeds...")
    
    # Save to JSON
    data = {
        'network': 'MoneroTrustedNetwork',
        'generated_at': time.time(),
        'total_seeds': len(seeds),
        'seeds': seeds
    }
    
    with open('/data/seeds/trusted_seeds.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    # Save to database
    conn = sqlite3.connect('/data/db/network.db')
    c = conn.cursor()
    
    for seed in seeds:
        c.execute('''
            INSERT OR REPLACE INTO trusted_seeds 
            (id, onion_address, trust_level, generated_at)
            VALUES (?, ?, ?, ?)
        ''', (seed['id'], seed['onion_address'], seed['trust_level'], seed['generated_at']))
    
    conn.commit()
    conn.close()
    
    print("✓ Generated 1000 trusted seeds")
    print("✓ Saved to /data/seeds/trusted_seeds.json")
    print("✓ Updated database")

if __name__ == '__main__':
    main()
