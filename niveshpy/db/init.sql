-- Database initialization script for NiveshPy
-- This script creates the necessary tables and sequences for the application.
-- This script is idempotent and can be run multiple times without causing errors.
-- It purposely avoids creating extra indices and constraints for better performance
-- during bulk data imports. Such constraints should be managed at the application level.
CREATE SEQUENCE IF NOT EXISTS account_id_seq;
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY DEFAULT nextval('account_id_seq'),
    name VARCHAR NOT NULL,
    institution VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata MAP(VARCHAR, VARCHAR) DEFAULT map()
);
CREATE TYPE IF NOT EXISTS SecurityType AS ENUM ('stock', 'bond', 'etf', 'mutual_fund', 'other');
CREATE TYPE IF NOT EXISTS SecurityCategory AS ENUM (
    'equity',
    'debt',
    'commodity',
    'real_estate',
    'other'
);
CREATE TABLE IF NOT EXISTS securities (
    key VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type SecurityType NOT NULL,
    category SecurityCategory NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata MAP(VARCHAR, VARCHAR) DEFAULT map()
);
CREATE TYPE IF NOT EXISTS TransactionType AS ENUM ('purchase', 'sale');
CREATE SEQUENCE IF NOT EXISTS transaction_id_seq;
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY DEFAULT nextval('transaction_id_seq'),
    transaction_date DATE,
    type TransactionType NOT NULL,
    description TEXT,
    amount DECIMAL(24, 2),
    units DECIMAL(24, 3),
    security_key TEXT,
    account_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata MAP(VARCHAR, VARCHAR) DEFAULT map()
);