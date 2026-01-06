CREATE TABLE IF NOT EXISTS trusted_seeds (
    id INTEGER PRIMARY KEY,
    onion_address TEXT UNIQUE NOT NULL,
    trust_level TEXT NOT NULL,
    generated_at REAL NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS untrusted_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    port INTEGER,
    reason TEXT,
    is_blocked BOOLEAN DEFAULT 1,
    UNIQUE(host, port)
);
