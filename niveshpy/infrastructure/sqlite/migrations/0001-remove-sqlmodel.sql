-- SQLModel support has been removed in favor of SQLAlchemy.  This migration 
-- updates the database schema to reflect the changes in the models.py file, 
-- which now uses SQLAlchemy instead of SQLModel.
-- 
-- 
-- Rename existing tables to temporary names:
ALTER TABLE account
RENAME TO account_old;

ALTER TABLE security
RENAME TO security_old;

ALTER TABLE "transaction"
RENAME TO transaction_old;

ALTER TABLE price
RENAME TO price_old;

-- Create new tables with updated schema:
CREATE TABLE
    account (
        id INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        institution VARCHAR NOT NULL,
        properties JSON NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uix_name_institution UNIQUE (name, institution)
    );

CREATE TABLE
    security (
        "key" VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        type VARCHAR(11) NOT NULL,
        category VARCHAR(11) NOT NULL,
        properties JSON NOT NULL,
        created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY ("key"),
        CONSTRAINT securitytype CHECK (
            type IN ('stock', 'bond', 'etf', 'mutual_fund', 'other')
        ),
        CONSTRAINT securitycategory CHECK (
            category IN (
                'equity',
                'debt',
                'commodity',
                'real_estate',
                'other'
            )
        )
    );

CREATE TABLE
    price (
        security_key VARCHAR NOT NULL,
        date DATE NOT NULL,
        open NUMERIC(24, 4) NOT NULL,
        high NUMERIC(24, 4) NOT NULL,
        low NUMERIC(24, 4) NOT NULL,
        close NUMERIC(24, 4) NOT NULL,
        properties JSON NOT NULL,
        created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (security_key, date),
        FOREIGN KEY (security_key) REFERENCES security ("key")
    );

CREATE TABLE
    IF NOT EXISTS "transaction" (
        id INTEGER NOT NULL,
        transaction_date DATE NOT NULL,
        type VARCHAR(8) NOT NULL,
        description VARCHAR NOT NULL,
        amount NUMERIC(24, 2) NOT NULL,
        units NUMERIC(24, 3) NOT NULL,
        security_key VARCHAR NOT NULL,
        account_id INTEGER NOT NULL,
        properties JSON NOT NULL,
        created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT transactiontype CHECK (type IN ('purchase', 'sale')),
        FOREIGN KEY (security_key) REFERENCES security ("key"),
        FOREIGN KEY (account_id) REFERENCES account (id)
    );

-- Migrate data from old tables to new tables
-- Convert created_at and created timestamps to UTC to match the new model's timezone-aware datetime
-- Convert enum values to lowercase to match the new model's enum values
INSERT INTO
    account (id, name, institution, properties, created_at)
SELECT
    id,
    name,
    institution,
    properties,
    datetime (created_at, 'utc') AS created_at -- Convert to UTC to match the new model's timezone-aware datetime
FROM
    account_old;

INSERT INTO
    security (
        "key",
        "name",
        "type",
        category,
        properties,
        created
    )
SELECT
    "key",
    "name",
    lower("type") AS "type", -- Convert enum values to lowercase to match the new model's enum values
    lower(category) AS category, -- Convert enum values to lowercase to match the new model's enum values
    properties,
    datetime (created, 'utc') AS created -- Convert to UTC to match the new model's timezone-aware datetime
FROM
    security_old;

INSERT INTO
    "transaction" (
        id,
        transaction_date,
        "type",
        "description",
        amount,
        units,
        security_key,
        account_id,
        properties,
        created
    )
SELECT
    id,
    transaction_date,
    lower("type") AS "type", -- Convert enum values to lowercase to match the new model's enum values
    "description",
    amount,
    units,
    security_key,
    account_id,
    properties,
    datetime (created, 'utc') AS created -- Convert to UTC to match the new model's timezone-aware datetime
FROM
    transaction_old;

INSERT INTO
    price (
        security_key,
        "date",
        open,
        high,
        low,
        close,
        properties,
        created
    )
SELECT
    security_key,
    "date",
    open,
    high,
    low,
    close,
    properties,
    datetime (created, 'utc') AS created -- Convert to UTC to match the new model's timezone-aware datetime
FROM
    price_old;

-- DROP OLD TABLES in order to avoid foreign key constraint issues during the migration
DROP TABLE transaction_old;

DROP TABLE price_old;

DROP TABLE security_old;

DROP TABLE account_old;