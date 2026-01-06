#!/usr/bin/env python3
"""
Mark all existing Monero nodes as UNTRUSTED.
Only our 1000 generated seeds are trusted.
"""
import json
import sqlite3
import time
import argparse
import requests
from pathlib import Path

class UntrustedNodeManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.known_untrusted = set()
        
    def load_known_monero_nodes(self):
        """Load known Monero nodes from various sources and mark as untrusted."""
        print("Loading known Monero nodes to mark as UNTRUSTED...")
        
        # Sources of known Monero nodes (to block)
        node_sources = [
            # Monero seed nodes
            'node.sethforprivacy.com:18080',
            'nodes.hashvault.pro:18080',
            'node.community.rino.io:18080',
            'selsta1.featherwallet.net:18080',
            'selsta2.featherwallet.net:18080',
            'node.monerodevs.org:18089',
            # Add more known nodes here
        ]
        
        # Load from external sources
        external_sources = [
            'https://raw.githubusercontent.com/monero-project/monero/master/src/p2p/net_node.inl',
            'https://raw.githubusercontent.com/monero-project/monero/master/src/p2p/seeds.txt'
        ]
        
        untrusted_nodes = []
        
        # Add hardcoded seed nodes
        for node in node_sources:
            if ':' in node:
                host, port = node.split(':')
                untrusted_nodes.append({
                    'host': host,
                    'port': int(port),
                    'source': 'monero_seeds',
                    'trust_level': 0,
                    'reason': 'Public seed node (not in trusted network)'
                })
        
        # Try to fetch from external sources
        for url in external_sources:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    lines = response.text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if ':' in line:
                                host, port = line.split(':')[:2]
                                if port.isdigit():
                                    untrusted_nodes.append({
                                        'host': host.strip(),
                                        'port': int(port),
                                        'source': url,
                                        'trust_level': 0,
                                        'reason': 'External Monero node'
                                    })
            except Exception as e:
                print(f"  Warning: Could not fetch from {url}: {e}")
        
        return untrusted_nodes
    
    def mark_all_as_untrusted(self, nodes):
        """Mark all nodes as untrusted in database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create untrusted nodes table
        c.execute('''
            CREATE TABLE IF NOT EXISTS untrusted_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                onion_address TEXT,
                source TEXT,
                trust_level INTEGER DEFAULT 0,
                reason TEXT,
                first_seen REAL,
                last_seen REAL,
                block_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT 1,
                UNIQUE(host, port)
            )
        ''')
        
        # Create block rules table
        c.execute('''
            CREATE TABLE IF NOT EXISTS block_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL,
                target TEXT NOT NULL,
                action TEXT DEFAULT 'BLOCK',
                created_at REAL,
                expires_at REAL,
                reason TEXT
            )
        ''')
        
        # Mark all nodes as untrusted
        current_time = time.time()
        for node in nodes:
            try:
                c.execute('''
                    INSERT OR REPLACE INTO untrusted_nodes 
                    (host, port, source, trust_level, reason, first_seen, last_seen, is_blocked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    node['host'],
                    node['port'],
                    node.get('source', 'manual'),
                    node.get('trust_level', 0),
                    node.get('reason', 'Not in trusted network'),
                    current_time,
                    current_time,
                    True
                ))
                
                # Create block rule
                c.execute('''
                    INSERT INTO block_rules 
                    (rule_type, target, action, created_at, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'host',
                    node['host'],
                    'BLOCK',
                    current_time,
                    'Not in trusted network'
                ))
                
            except sqlite3.IntegrityError:
                # Already exists, update last_seen
                c.execute('''
                    UPDATE untrusted_nodes 
                    SET last_seen = ?, block_count = block_count + 1
                    WHERE host = ? AND port = ?
                ''', (current_time, node['host'], node['port']))
        
        conn.commit()
        
        # Count untrusted nodes
        c.execute('SELECT COUNT(*) FROM untrusted_nodes WHERE is_blocked = 1')
        count = c.fetchone()[0]
        
        conn.close()
        
        print(f"✓ Marked {count} nodes as UNTRUSTED")
        print(f"✓ Created block rules for all untrusted nodes")
        
        return count
    
    def create_untrusted_policy(self):
        """Create comprehensive untrusted node policy."""
        policy = {
            'policy_name': 'ExclusiveTrustNetwork',
            'version': '1.0',
            'created_at': time.time(),
            'trust_policy': 'EXCLUSIVE',
            'trusted_nodes': 'Only our 1000 generated seeds',
            'untrusted_nodes': 'ALL other Monero nodes',
            'default_action': 'BLOCK',
            'exceptions': 'None',
            'rules': [
                {
                    'rule': 'BLOCK_ALL_EXTERNAL',
                    'description': 'Block all nodes not in trusted seed list',
                    'action': 'REJECT',
                    'priority': 'HIGHEST'
                },
                {
                    'rule': 'TRUST_ONLY_WHITELIST',
                    'description': 'Only allow connections from whitelisted seeds',
                    'action': 'ACCEPT',
                    'priority': 'HIGH'
                },
                {
                    'rule': 'LOG_ALL_BLOCKED',
                    'description': 'Log all blocked connection attempts',
                    'action': 'LOG',
                    'priority': 'MEDIUM'
                }
            ]
        }
        
        return policy
    
    def generate_iptables_rules(self):
        """Generate iptables rules to block untrusted nodes."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get all untrusted hosts to block
        c.execute('SELECT DISTINCT host FROM untrusted_nodes WHERE host NOT LIKE "%.onion"')
        hosts = [row[0] for row in c.fetchall()]
        
        conn.close()
        
        rules = []
        rules.append("# ===== MONERO TRUSTED NETWORK FIREWALL =====\n")
        rules.append("# BLOCK all non-trusted nodes\n")
        rules.append("# Generated: " + time.ctime() + "\n")
        
        # Create iptables rules for each host
        for host in hosts:
            # Try to resolve IP if it's a domain
            import socket
            try:
                ip = socket.gethostbyname(host)
                rules.append(f"# Block {host} ({ip})")
                rules.append(f"iptables -A INPUT -s {ip} -j DROP")
                rules.append(f"iptables -A OUTPUT -d {ip} -j DROP")
            except:
                rules.append(f"# Could not resolve {host}")
        
        rules.append("\n# Allow only Tor traffic (for trusted .onion seeds)")
        rules.append("iptables -A OUTPUT -o lo -j ACCEPT")
        rules.append("iptables -A OUTPUT -m owner --uid-owner debian-tor -j ACCEPT")
        rules.append("iptables -A OUTPUT -d 127.0.0.1 -j ACCEPT")
        rules.append("iptables -A OUTPUT -j DROP  # Block all other outbound")
        
        return '\n'.join(rules)

def main():
    parser = argparse.ArgumentParser(description='Mark all Monero nodes as untrusted')
    parser.add_argument('--db', type=str, required=True, help='Database file')
    parser.add_argument('--init', action='store_true', help='Initialize with known nodes')
    parser.add_argument('--generate-firewall', action='store_true', help='Generate firewall rules')
    parser.add_argument('--output', type=str, help='Output file for firewall rules')
    
    args = parser.parse_args()
    
    manager = UntrustedNodeManager(args.db)
    
    if args.init:
        # Load known nodes and mark as untrusted
        nodes = manager.load_known_monero_nodes()
        count = manager.mark_all_as_untrusted(nodes)
        
        # Create policy file
        policy = manager.create_untrusted_policy()
        policy_file = Path(args.db).parent / 'untrusted_policy.json'
        with open(policy_file, 'w') as f:
            json.dump(policy, f, indent=2)
        
        print(f"✓ Created untrusted node policy: {policy_file}")
        print()
        print("=" * 80)
        print("UNTRUSTED NODE POLICY APPLIED")
        print("=" * 80)
        print(f"Total nodes marked as UNTRUSTED: {count}")
        print("Only our 1000 generated seeds are TRUSTED")
        print("All other nodes are explicitly BLOCKED")
    
    if args.generate_firewall:
        rules = manager.generate_iptables_rules()
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(rules)
            print(f"✓ Generated firewall rules: {args.output}")
        else:
            print(rules)

if __name__ == '__main__':
    main()
