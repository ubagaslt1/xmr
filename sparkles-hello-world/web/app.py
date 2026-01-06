#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import json
import time
import sqlite3
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'Monero Trusted Network'
    })

@app.route('/api/stats')
def stats():
    try:
        conn = sqlite3.connect('/data/db/network.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM trusted_seeds')
        trusted_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM untrusted_nodes WHERE is_blocked = 1')
        untrusted_count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'trusted_seeds': trusted_count,
            'untrusted_nodes': untrusted_count,
            'network': 'MoneroTrustedNetwork',
            'policy': 'exclusive'
        })
    except:
        return jsonify({'error': 'Database not ready'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
