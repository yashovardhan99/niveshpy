CREATE SEQUENCE IF NOT EXISTS account_id_seq;
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY DEFAULT nextval('account_id_seq'),
    name VARCHAR NOT NULL,
    institution VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS securities (
    key VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    category VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    transaction_date DATE,
    type TEXT,
    description TEXT,
    amount DECIMAL(24, 2),
    units DECIMAL(24, 3),
    security_key TEXT,
    account_key TEXT
);
