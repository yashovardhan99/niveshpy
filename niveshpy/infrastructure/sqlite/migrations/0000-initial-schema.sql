CREATE TABLE
    IF NOT EXISTS account (
        id INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        institution VARCHAR NOT NULL,
        properties JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uix_name_institution UNIQUE (name, institution)
    );

CREATE TABLE
    IF NOT EXISTS security (
        "key" VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        type VARCHAR(11) NOT NULL,
        category VARCHAR(11) NOT NULL,
        properties JSON NOT NULL,
        created DATETIME NOT NULL,
        PRIMARY KEY ("key")
    );

CREATE TABLE
    IF NOT EXISTS price (
        security_key VARCHAR NOT NULL,
        date DATE NOT NULL,
        open NUMERIC(24, 4) NOT NULL,
        high NUMERIC(24, 4) NOT NULL,
        low NUMERIC(24, 4) NOT NULL,
        close NUMERIC(24, 4) NOT NULL,
        properties JSON NOT NULL,
        created DATETIME NOT NULL,
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
        created DATETIME NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (security_key) REFERENCES security ("key"),
        FOREIGN KEY (account_id) REFERENCES account (id)
    );