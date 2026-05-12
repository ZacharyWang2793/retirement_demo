-- Retirement account support demo schema.
-- Every table the transaction taxonomy needs is defined here.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id              TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    dob             TEXT NOT NULL,           -- ISO yyyy-mm-dd
    ssn_last4       TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT NOT NULL,
    address_line1   TEXT NOT NULL,
    address_line2   TEXT,
    address_city    TEXT NOT NULL,
    address_state   TEXT NOT NULL,           -- 2-letter US state
    address_postal  TEXT NOT NULL,
    address_country TEXT NOT NULL DEFAULT 'US'
);

CREATE TABLE IF NOT EXISTS users (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL UNIQUE,
    email               TEXT NOT NULL,
    password_hash_mock  TEXT NOT NULL,
    mfa_enabled         INTEGER NOT NULL DEFAULT 0,
    last_login_at       TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS accounts (
    id              TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    account_type    TEXT NOT NULL,           -- 401k|roth_401k|ira_traditional|ira_roth|sep_ira|simple_ira
    plan_name       TEXT NOT NULL,
    balance         REAL NOT NULL,
    vested_balance  REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    opened_date     TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS beneficiaries (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    type            TEXT NOT NULL,           -- primary|contingent
    name            TEXT NOT NULL,
    relationship    TEXT NOT NULL,
    dob             TEXT NOT NULL,
    ssn_last4       TEXT NOT NULL,
    allocation_pct  REAL NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS investments (
    id                     TEXT PRIMARY KEY,
    account_id             TEXT NOT NULL,
    fund_ticker            TEXT NOT NULL,
    fund_name              TEXT NOT NULL,
    shares                 REAL NOT NULL,
    current_value          REAL NOT NULL,
    target_allocation_pct  REAL NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Standing contribution election. Actual money-in events live in `transactions`.
CREATE TABLE IF NOT EXISTS contributions (
    id                  TEXT PRIMARY KEY,
    account_id          TEXT NOT NULL UNIQUE,
    contribution_pct    REAL NOT NULL,
    employer_match_pct  REAL NOT NULL,
    effective_date      TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id           TEXT PRIMARY KEY,
    account_id   TEXT NOT NULL,
    txn_date     TEXT NOT NULL,
    txn_type     TEXT NOT NULL,              -- contribution|distribution|fee|dividend|rollover_in|rollover_out
    amount       REAL NOT NULL,
    fund_ticker  TEXT,
    description  TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS loans (
    id                TEXT PRIMARY KEY,
    account_id        TEXT NOT NULL,
    principal         REAL NOT NULL,
    interest_rate     REAL NOT NULL,
    term_months       INTEGER NOT NULL,
    outstanding       REAL NOT NULL,
    status            TEXT NOT NULL,          -- active|paid_off|defaulted
    next_payment_due  TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS distributions (
    id            TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    type          TEXT NOT NULL,              -- rmd|hardship|qualified|rollover_out
    amount        REAL NOT NULL,
    status        TEXT NOT NULL,              -- pending|completed|rejected
    requested_at  TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS tax_withholding (
    account_id    TEXT NOT NULL,
    tax_year      INTEGER NOT NULL,
    federal_pct   REAL NOT NULL,
    state_code    TEXT,
    state_pct     REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, tax_year),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    id                      TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL,
    nickname                TEXT NOT NULL,
    routing_number_last4    TEXT NOT NULL,
    account_number_last4    TEXT NOT NULL,
    account_type            TEXT NOT NULL,    -- checking|savings
    is_default              INTEGER NOT NULL DEFAULT 0,
    verified_at             TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,              -- statement_quarterly|statement_annual|1099r|1099q
    period_start  TEXT NOT NULL,
    period_end    TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    generated_at  TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS delivery_prefs (
    customer_id           TEXT PRIMARY KEY,
    paperless_statements  INTEGER NOT NULL DEFAULT 0,
    paperless_tax         INTEGER NOT NULL DEFAULT 0,
    marketing_email       INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS requests (
    id                 TEXT PRIMARY KEY,
    client_request_id  TEXT NOT NULL UNIQUE,  -- idempotency key
    customer_id        TEXT NOT NULL,
    type               TEXT NOT NULL,
    status             TEXT NOT NULL,         -- pending|completed|cancelled|rejected
    payload_json       TEXT NOT NULL,
    routing_target     TEXT NOT NULL DEFAULT 'self_service',
    created_at         TEXT NOT NULL,
    resolved_at        TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL,
    thread_id    TEXT,
    action       TEXT NOT NULL,
    before_json  TEXT,
    after_json   TEXT,
    occurred_at  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_account ON beneficiaries(account_id);
CREATE INDEX IF NOT EXISTS idx_investments_account ON investments(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id, txn_date DESC);
CREATE INDEX IF NOT EXISTS idx_requests_customer ON requests(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_customer ON audit_log(customer_id, occurred_at DESC);
