-- Based on my own usage, I found that a new transaction type called "reversal"
-- was needed to support the reversal of a transaction.  This migration adds the
-- "reversal" transaction type to the "transaction" table along with a new 
-- is_ignored flag and updates the existing transactions to use the new 
-- "reversal" type where appropriate.
-- 
-- 
-- Rename existing table to temporary names:
ALTER TABLE "transaction"
RENAME TO transaction_old;

-- Create new table with updated schema:
CREATE TABLE
    "transaction" (
        id INTEGER NOT NULL,
        transaction_date DATE NOT NULL,
        "type" VARCHAR(8) NOT NULL,
        "description" VARCHAR NOT NULL,
        amount NUMERIC(24, 2) NOT NULL,
        units NUMERIC(24, 3) NOT NULL,
        security_key VARCHAR NOT NULL,
        account_id INTEGER NOT NULL,
        properties JSON NOT NULL,
        created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        is_ignored BOOLEAN DEFAULT FALSE NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT transactiontype CHECK ("type" IN ('purchase', 'sale', 'reversal')),
        FOREIGN KEY (security_key) REFERENCES security ("key"),
        FOREIGN KEY (account_id) REFERENCES account (id)
    );

-- Migrate data from old table to new table
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
        created,
        is_ignored
    )
SELECT
    id,
    transaction_date,
    "type",
    "description",
    amount,
    units,
    security_key,
    account_id,
    properties,
    created,
    FALSE AS is_ignored
FROM
    transaction_old;

-- Update existing transactions to use the new "reversal" type where appropriate
-- This should work for transactions parsed by casparser.
UPDATE "transaction"
SET
    "type" = 'reversal'
WHERE
    json_extract (properties, '$.original_type') = 'REVERSAL';

-- DROP OLD TABLE
DROP TABLE transaction_old;