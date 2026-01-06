#!/usr/bin/env python3
"""
Enforce the trusted network policy.
Continuously monitors and blocks untrusted connections.
"""
import json
import sqlite3
import time
import subprocess
import argparse
from pathlib import Path
import signal
import sys

class TrustEnforcer:
    def __init__(self, db_path, check_interval=60):
        self.db_path = db_path
        self.check_interval = check_interval
        self.running = True
        
        # Signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        print("\nTrust enforcer shutting down...")
        self.running = False
    
    def get_current_connections(self):
        """Get current network connections to monerod."""
        connections = []
        
        try:
            # Use netstat to find connections to monerod ports
            result = subprocess.run(
                ['netstat', '-tpn', '2>/dev/null | grep monerod || true'],
                shell=True,
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 5:
                        local = parts[3]
                        remote = parts[4]
                        
                        # Extract IP and port
                        if ':' in remote:
                            remote_ip, remote_port = remote.rsplit(':', 1)
                            connections.append({
                                'remote_ip': remote_ip,
                                'remote_port': remote_port,
                                'local_port': local.split(':')[-1],
                                'state': parts[5] if len(parts) > 5 else 'UNKNOWN'
                            })
        
        except Exception as e:
            print(f"Error getting connections: {e}")
        
        return connections
    
    def check_connection_trust(self, connection):
        """Check if a connection is from a trusted source."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Check if this IP is in untrusted list
        c.execute('''
            SELECT host, reason FROM untrusted_nodes 
            WHERE host = ? AND is_blocked = 1
        ''', (connection['remote_ip'],))
        
        untrusted = c.fetchone()
        
        if untrusted:
            conn.close()
            return {
                'trusted': False,
                'reason': f"IP {connection['remote_ip']} is untrusted: {untrusted[1]}"
            }
        
        # Check if this is a trusted onion connection
        # (We would need to map IP to onion address, simplified here)
        
        conn.close()
        
        # Default: untrusted (only trusted if explicitly in our seed list)
        return {
            'trusted': False,
            'reason': 'Not in trusted seed list'
        }
    
    def block_untrusted_connection(self, connection, reason):
        """Block an untrusted connection."""
        print(f"🚫 BLOCKING untrusted connection: {connection['remote_ip']}:{connection['remote_port']}")
        print(f"   Reason: {reason}")
        
        # Add to firewall block list
        try:
            # Block with iptables
            subprocess.run([
                'iptables', '-A', 'INPUT', '-s', connection['remote_ip'], '-j', 'DROP'
            ], check=False)
            
            subprocess.run([
                'iptables', '-A', 'OUTPUT', '-d', connection['remote_ip'], '-j', 'DROP'
            ], check=False)
            
            # Log the block
            self.log_block(connection, reason)
            
        except Exception as e:
            print(f"   Error blocking connection: {e}")
    
    def log_block(self, connection, reason):
        """Log blocked connection to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO blocked_connections 
            (timestamp, remote_ip, remote_port, reason, action)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            time.time(),
            connection['remote_ip'],
            connection['remote_port'],
            reason,
            'BLOCK'
        ))
        
        # Update untrusted node stats
        c.execute('''
            UPDATE untrusted_nodes 
            SET block_count = block_count + 1, last_seen = ?
            WHERE host = ?
        ''', (time.time(), connection['remote_ip']))
        
        conn.commit()
        conn.close()
    
    def enforce_trust_policy(self):
        """Main enforcement loop."""
        print("🔒 Starting trust enforcement daemon...")
        print("Only connections from trusted seeds will be allowed.")
        print("All other connections will be blocked.")
        print()
        
        while self.running:
            try:
                # Get current connections
                connections = self.get_current_connections()
                
                if connections:
                    print(f"Checking {len(connections)} active connections...")
                    
                    for conn in connections:
                        trust_check = self.check_connection_trust(conn)
                        
                        if not trust_check['trusted']:
                            self.block_untrusted_connection(conn, trust_check['reason'])
                        else:
                            print(f"✓ Trusted connection: {conn['remote_ip']}:{conn['remote_port']}")
                
                # Sleep before next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Error in enforcement loop: {e}")
                time.sleep(5)
    
    def run_daemon(self):
        """Run as a daemon."""
        # Create necessary database tables
        self.init_database()
        
        # Run enforcement
        self.enforce_trust_policy()
    
    def init_database(self):
        """Initialize database tables if needed."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create blocked connections table
        c.execute('''
            CREATE TABLE IF NOT EXISTS blocked_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                remote_ip TEXT NOT NULL,
                remote_port INTEGER,
                reason TEXT,
                action TEXT,
                rule_applied TEXT
            )
        ''')
        
        # Create enforcement log
        c.execute('''
            CREATE TABLE IF NOT EXISTS enforcement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                result TEXT,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Enforce trusted network policy')
    parser.add_argument('--db', type=str, default='/data/db/network.db', help='Database file')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
