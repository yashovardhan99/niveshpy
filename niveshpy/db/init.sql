CREATE SEQUENCE IF NOT EXISTS account_id_seq;
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY DEFAULT nextval('account_id_seq'),
    name VARCHAR NOT NULL,
    institution VARCHAR NOT NULL
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
    category SecurityCategory NOT NULL
);
CREATE TYPE IF NOT EXISTS TransactionType AS ENUM ('purchase', 'sale');
CREATE TABLE IF NOT EXISTS transactions (
    transaction_date DATE,
    type TransactionType NOT NULL,
    description TEXT,
    amount DECIMAL(24, 2),
    units DECIMAL(24, 3),
    security_key TEXT,
    account_key TEXT
);