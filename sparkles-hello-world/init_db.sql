-- Monero Trusted Network Database
-- Only 1000 seeds are trusted, all others are untrusted

-- Trusted Seeds (ONLY these 1000 are trusted)
CREATE TABLE IF NOT EXISTS trusted_seeds (
    id INTEGER PRIMARY KEY,
    onion_address TEXT UNIQUE NOT NULL,
    private_key TEXT NOT NULL,
    public_key TEXT NOT NULL,
    trust_level TEXT NOT NULL CHECK(trust_level IN ('platinum', 'gold', 'silver', 'bronze')),
    trust_score INTEGER DEFAULT 100 CHECK(trust_score BETWEEN 0 AND 100),
    certificate TEXT NOT NULL,
    ports TEXT NOT NULL,
    generated_at REAL NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    last_seen REAL,
    connection_count INTEGER DEFAULT 0,
    total_uptime REAL DEFAULT 0,
    last_error TEXT,
    network_name TEXT DEFAULT 'MoneroTrustedNetwork'
);

-- Untrusted Nodes (ALL other Monero nodes)
CREATE TABLE IF NOT EXISTS untrusted_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    onion_address TEXT,
    source TEXT,
    trust_level INTEGER DEFAULT 0 CHECK(trust_level BETWEEN -100 AND 0),
    reason TEXT,
    first_seen REAL,
    last_seen REAL,
    block_count INTEGER DEFAULT 0,
    is_blocked BOOLEAN DEFAULT 1,
    UNIQUE(host, port)
);

-- Block Rules
CREATE TABLE IF NOT EXISTS block_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL CHECK(rule_type IN ('host', 'ip', 'subnet', 'country')),
    target TEXT NOT NULL,
    action TEXT DEFAULT 'BLOCK' CHECK(action IN ('BLOCK', 'ALLOW', 'LOG')),
    created_at REAL NOT NULL,
    expires_at REAL,
    reason TEXT,
    priority INTEGER DEFAULT 50
);

-- Blocked Connections Log
CREATE TABLE IF NOT EXISTS blocked_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    remote_ip TEXT NOT NULL,
    remote_port INTEGER,
    reason TEXT,
    action TEXT,
    rule_applied TEXT
);

-- Network Statistics
CREATE TABLE IF NOT EXISTS network_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    trusted_connections INTEGER DEFAULT 0,
    blocked_connections INTEGER DEFAULT 0,
    total_untrusted_nodes INTEGER DEFAULT 0,
    avg_trust_score REAL,
    enforcement_actions INTEGER DEFAULT 0
);

-- Trust Certificates (for verification)
CREATE TABLE IF NOT EXISTS trust_certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_id INTEGER NOT NULL,
    certificate_hash TEXT UNIQUE NOT NULL,
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    issuer TEXT NOT NULL,
    revoked BOOLEAN DEFAULT 0,
    revoked_at REAL,
    FOREIGN KEY (seed_id) REFERENCES trusted_seeds (id)
);

-- Indexes for performance
CREATE INDEX idx_trusted_seeds_active ON trusted_seeds(is_active, trust_level);
CREATE INDEX idx_trusted_seeds_address ON trusted_seeds(onion_address);
CREATE INDEX idx_untrusted_blocked ON untrusted_nodes(is_blocked, trust_level);
CREATE INDEX idx_untrusted_host ON untrusted_nodes(host);
CREATE INDEX idx_block_rules_active ON block_rules(expires_at, priority) WHERE expires_at IS NULL OR expires_at > unixepoch();
CREATE INDEX idx_blocked_connections_time ON blocked_connections(timestamp);

-- Views
CREATE VIEW IF NOT EXISTS network_status AS
SELECT 
    (SELECT COUNT(*) FROM trusted_seeds WHERE is_active = 1) as trusted_seeds_active,
    (SELECT COUNT(*) FROM untrusted_nodes WHERE is_blocked = 1) as untrusted_nodes_blocked,
    (SELECT COUNT(*) FROM blocked_connections 
     WHERE timestamp > unixepoch('now', '-1 day')) as blocked_last_24h,
    (SELECT AVG(trust_score) FROM trusted_seeds WHERE is_active = 1) as avg_trust_score;

CREATE VIEW IF NOT EXISTS trust_violations AS
SELECT 
    bc.timestamp,
    bc.remote_ip,
    bc.remote_port,
    bc.reason,
    un.host as known_host,
    un.reason as host_reason
FROM blocked_connections bc
LEFT JOIN untrusted_nodes un ON bc.remote_ip = un.host
ORDER BY bc.timestamp DESC;

-- Initialize with default block rules
INSERT OR IGNORE INTO block_rules (rule_type, target, action, created_at, reason, priority)
VALUES 
    ('subnet', '0.0.0.0/0', 'BLOCK', unixepoch(), 'Default: Block all external', 10),
    ('host', '127.0.0.1', 'ALLOW', unixepoch(), 'Allow localhost', 100),
    ('host', 'localhost', 'ALLOW', unixepoch(), 'Allow localhost', 100);

-- Create trigger to auto-block new untrusted nodes
CREATE TRIGGER IF NOT EXISTS auto_block_untrusted
AFTER INSERT ON untrusted_nodes
FOR EACH ROW
WHEN NEW.is_blocked = 1
BEGIN
    INSERT INTO block_rules (rule_type, target, action, created_at, reason)
    VALUES ('host', NEW.host, 'BLOCK', unixepoch(), 
            COALESCE(NEW.reason, 'Auto-blocked untrusted node'));
END;
