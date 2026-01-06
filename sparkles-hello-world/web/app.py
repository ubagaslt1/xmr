#!/usr/bin/env python3
"""
Web interface for Monero Trusted Network.
Shows trusted seeds and blocked untrusted nodes.
"""
from flask import Flask, render_template, jsonify, request, send_file
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
import humanize

app = Flask(__name__, static_folder='static', template_folder='templates')

DB_PATH = Path('/data/db/network.db')

@app.route('/')
def index():
    """Main dashboard showing trusted network status."""
    return render_template('index.html')

@app.route('/api/trusted/seeds')
def get_trusted_seeds():
    """Get all trusted seeds."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''
            SELECT id, onion_address, trust_level, trust_score, 
                   is_active, last_seen, connection_count, total_uptime
            FROM trusted_seeds
            ORDER BY trust_level, trust_score DESC
        ''')
        
        seeds = [dict(row) for row in c.fetchall()]
        
        # Get trust statistics
        c.execute('SELECT COUNT(*) as total, AVG(trust_score) as avg_score FROM trusted_seeds')
        stats = dict(c.fetchone())
        
        c.execute('SELECT trust_level, COUNT(*) as count FROM trusted_seeds GROUP BY trust_level')
        levels = {row[0]: row[1] for row in c.fetchall()}
        
        conn.close()
        
        return jsonify({
            'success': True,
            'network': 'MoneroTrustedNetwork',
            'policy': 'EXCLUSIVE_TRUST',
            'stats': stats,
            'trust_levels': levels,
            'seeds': seeds,
            'total': len(seeds)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/untrusted/nodes')
def get_untrusted_nodes():
    """Get all untrusted nodes."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        offset = (page - 1) * per_page
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''
            SELECT id, host, port, source, trust_level, reason, 
                   first_seen, last_seen, block_count, is_blocked
            FROM untrusted_nodes
            WHERE is_blocked = 1
            ORDER BY block_count DESC, last_seen DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset))
        
        nodes = [dict(row) for row in c.fetchall()]
        
        # Get total count
        c.execute('SELECT COUNT(*) as total FROM untrusted_nodes WHERE is_blocked = 1')
        total = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'nodes': nodes,
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/stats')
def get_network_stats():
    """Get comprehensive network statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get stats from views
        c.execute('SELECT * FROM network_status')
        status = dict(c.fetchone())
        
        # Get 24h activity
        day_ago = time.time() - 86400
        c.execute('''
            SELECT 
                COUNT(*) as total_blocks,
                COUNT(DISTINCT remote_ip) as unique_ips,
                MIN(timestamp) as first_block,
                MAX(timestamp) as last_block
            FROM blocked_connections
            WHERE timestamp > ?
        ''', (day_ago,))
        
        blocks_24h = dict(c.fetchone())
        
        # Get trust distribution
        c.execute('''
            SELECT trust_level, COUNT(*) as count, AVG(trust_score) as avg_score
            FROM trusted_seeds 
            WHERE is_active = 1
            GROUP BY trust_level
        ''')
        
        trust_dist = {}
        for row in c.fetchall():
            trust_dist[row[0]] = {'count': row[1], 'avg_score': row[2]}
        
        conn.close()
        
        return jsonify({
            'success': True,
            'timestamp': time.time(),
            'network_status': status,
            'blocks_24h': blocks_24h,
            'trust_distribution': trust_dist,
            'policy': {
                'name': 'Exclusive Trust Network',
                'trusted_seeds': 1000,
                'all_others': 'UNTRUSTED',
                'enforcement': 'ACTIVE'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blocked/recent')
def get_recent_blocks():
    """Get recently blocked connections."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''
            SELECT timestamp, remote_ip, remote_port, reason, action
            FROM blocked_connections
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        
        blocks = []
        for row in c.fetchall():
            block = dict(row)
            block['time_ago'] = humanize.naturaltime(datetime.fromtimestamp(block['timestamp']))
            blocks.append(block)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'blocks': blocks,
            'total': len(blocks)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/trusted')
def get_trusted_config():
    """Get configuration file with only trusted seeds."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get trusted seeds for config
        c.execute('''
            SELECT onion_address, ports
            FROM trusted_seeds
            WHERE is_active = 1
            ORDER BY trust_level DESC, trust_score DESC
            LIMIT 1000
        ''')
        
        config = "# MONERO TRUSTED NETWORK CONFIGURATION\n"
        config += "# Generated: " + datetime.now().isoformat() + "\n"
        config += "# Policy: EXCLUSIVE - Only these seeds are trusted\n"
        config += "# All other nodes are UNTRUSTED\n\n"
        
        config += "p2p-bind-ip=0.0.0.0\n"
        config += "p2p-bind-port=18080\n"
        config += "rpc-bind-ip=0.0.0.0\n"
        config += "rpc-bind-port=18089\n\n"
        
        config += "# ===== TRUSTED SEEDS ONLY =====\n"
        config += "# Platinum (Highest Trust)\n"
        
        c.execute('''
            SELECT onion_address, ports
            FROM trusted_seeds
            WHERE trust_level = 'platinum' AND is_active = 1
            ORDER BY id
        ''')
        
        for row in c.fetchall():
            ports = json.loads(row[1])
            config += f"add-priority-node={row[0]}:{ports['p2p']}\n"
        
        config += "\n# Gold\n"
        c.execute('''
            SELECT onion_address, ports
            FROM trusted_seeds
            WHERE trust_level = 'gold' AND is_active = 1
            ORDER BY id
        ''')
        
        for row in c.fetchall():
            ports = json.loads(row[1])
            config += f"add-exclusive-peer={row[0]}:{ports['p2p']}\n"
        
        config += "\n# Silver & Bronze\n"
        config += "# (First 200 as regular peers)\n"
        
        c.execute('''
            SELECT onion_address, ports
            FROM trusted_seeds
            WHERE trust_level IN ('silver', 'bronze') AND is_active = 1
            ORDER BY id
            LIMIT 200
        ''')
        
        for row in c.fetchall():
            ports = json.loads(row[1])
            config += f"add-peer={row[0]}:{ports['p2p']}\n"
        
        config += "\n# ===== SECURITY =====\n"
        config += "no-igd=1\n"
        config += "disable-dns-checkpoints=1\n"
        config += "out-peers=64\n"
        config += "in-peers=1024\n\n"
        
        config += "# ===== TOR =====\n"
        config += "tx-proxy=tor,127.0.0.1:9050,16\n"
        
        conn.close()
        
        response = app.response_class(
            response=config,
            mimetype='text/plain'
        )
        
        response.headers['Content-Disposition'] = 'attachment; filename=monerod.trusted.conf'
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/trusted')
def export_trusted_seeds():
    """Export trusted seeds list."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''
            SELECT onion_address, ports
            FROM trusted_seeds
            WHERE is_active = 1
            ORDER BY id
        ''')
        
        seeds = []
        for row in c.fetchall():
            ports = json.loads(row[1])
            seeds.append(f"{row[0]}:{ports['p2p']}")
        
        conn.close()
        
        response = app.response_class(
            response='\n'.join(seeds),
            mimetype='text/plain'
        )
        
        response.headers['Content-Disposition'] = 'attachment; filename=trusted_seeds.txt'
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check endpoint."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check database
        c.execute('SELECT COUNT(*) FROM trusted_seeds')
        trusted_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM untrusted_nodes WHERE is_blocked = 1')
        untrusted_count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'trusted_seeds': trusted_count,
            'untrusted_nodes': untrusted_count,
            'policy_enforced': True,
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
