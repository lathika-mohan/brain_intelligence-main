-- Phase 5A Postgres init - seed assets for Stage 2 validation
CREATE TABLE IF NOT EXISTS assets (
    id VARCHAR(100) PRIMARY KEY,
    asset_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    location VARCHAR(255),
    criticality VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO assets (id, asset_id, name, type, status, location, criticality) VALUES
('machine07', 'machine07', 'Pump-007 Bearing Assembly', 'PUMP', 'OPERATIONAL', 'Plant-A / Sector-3', 'HIGH'),
('machine01', 'machine01', 'Compressor-001', 'COMPRESSOR', 'DEGRADED', 'Plant-A / Sector-1', 'CRITICAL'),
('machine02', 'machine02', 'Turbine-002', 'TURBINE', 'OPERATIONAL', 'Plant-B / Sector-2', 'MEDIUM'),
('pump101', 'pump101', 'Pump-101 Main Feed', 'PUMP', 'OPERATIONAL', 'Plant-A', 'HIGH'),
('asset-101', 'asset-101', 'Motor Assembly 101', 'MOTOR', 'OPERATIONAL', 'Plant-C', 'LOW')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(100) PRIMARY KEY,
    asset_id VARCHAR(100) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    severity VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(100) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (id, username, password_hash, role) VALUES
('user-demo', 'demo_operator', '$2b$12$demo_hashed_secure_password_2026', 'OPERATOR')
ON CONFLICT (id) DO NOTHING;
