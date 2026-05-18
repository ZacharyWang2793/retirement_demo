"""Seed 3 deterministic demo customers.

Run: `python -m data.seed`
Wipes the DB first so reruns are stable.
"""
from __future__ import annotations

import sys

from db.connection import get_db, reset_db


DEMO_CUSTOMERS = [
    {
        "id": "demo-001",
        "first_name": "Margaret",
        "last_name": "Chen",
        "dob": "1965-04-12",
        "ssn_last4": "6789",
        "email": "margaret.chen@example.com",
        "phone": "415-555-0142",
        "address_line1": "1820 Filbert Street",
        "address_line2": "Apt 4",
        "address_city": "San Francisco",
        "address_state": "CA",
        "address_postal": "94123",
    },
    {
        "id": "demo-002",
        "first_name": "Tyler",
        "last_name": "Rodriguez",
        "dob": "1989-08-23",
        "ssn_last4": "4321",
        "email": "tyler.rodriguez@example.com",
        "phone": "512-555-0188",
        "address_line1": "44 Lakeview Drive",
        "address_line2": None,
        "address_city": "Austin",
        "address_state": "TX",
        "address_postal": "78704",
    },
    {
        "id": "demo-003",
        "first_name": "Nina",
        "last_name": "Patel",
        "dob": "1996-11-04",
        "ssn_last4": "1122",
        "email": "nina.patel@example.com",
        "phone": "212-555-0173",
        "address_line1": "112 Greene Street",
        "address_line2": "Floor 3",
        "address_city": "New York",
        "address_state": "NY",
        "address_postal": "10012",
    },
]


def _insert_customer(conn, c):
    conn.execute(
        """
        INSERT INTO customers (id, first_name, last_name, dob, ssn_last4, email, phone,
                               address_line1, address_line2, address_city, address_state,
                               address_postal, address_country)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'US')
        """,
        (c["id"], c["first_name"], c["last_name"], c["dob"], c["ssn_last4"], c["email"], c["phone"],
         c["address_line1"], c["address_line2"], c["address_city"], c["address_state"], c["address_postal"]),
    )
    conn.execute(
        """
        INSERT INTO users (id, customer_id, email, password_hash_mock, mfa_enabled, last_login_at)
        VALUES (?, ?, ?, 'mock-hash', 1, ?)
        """,
        (f"usr-{c['id']}", c["id"], c["email"], "2026-05-18T11:30:00Z"),
    )
    conn.execute(
        """
        INSERT INTO delivery_prefs (customer_id, paperless_statements, paperless_tax, marketing_email)
        VALUES (?, 1, 0, 1)
        """,
        (c["id"],),
    )
    # Two enrolled MFA devices per customer so the remove-flow demo has options.
    conn.executemany(
        """
        INSERT INTO mfa_devices (id, customer_id, kind, label, contact, enrolled_at, last_used_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        [
            (f"mfa-{c['id']}-sms", c["id"], "sms", "Primary phone", c["phone"], "2024-02-12T09:14:00Z", "2026-05-17T08:01:00Z"),
            (f"mfa-{c['id']}-totp", c["id"], "totp", "Authenticator app", None, "2024-09-30T12:00:00Z", "2026-05-16T18:42:00Z"),
        ],
    )
    # One pending request so check_request_status / cancel_request demos have data.
    conn.execute(
        """
        INSERT INTO requests (id, client_request_id, customer_id, type, status,
                              payload_json, routing_target, created_at, resolved_at)
        VALUES (?, ?, ?, ?, 'pending', ?, 'self_service', ?, NULL)
        """,
        (
            f"req-seed-{c['id']}",
            f"seed-{c['id']}-pending",
            c["id"],
            "change_phone",
            '{"phone": "555-555-0001"}',
            "2026-05-15T10:20:00Z",
        ),
    )


def _seed_demo_001(conn):
    # Margaret: near-retiree, two accounts with funds, beneficiary, RMD-eligible.
    conn.executemany(
        "INSERT INTO accounts (id, customer_id, account_type, plan_name, balance, vested_balance, status, opened_date) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("acc-001a", "demo-001", "401k", "Acme Industries 401(k)", 612400.50, 612400.50, "active", "1995-03-15"),
            ("acc-001b", "demo-001", "ira_traditional", "Personal Traditional IRA", 184250.00, 184250.00, "active", "2008-01-10"),
        ],
    )
    conn.executemany(
        "INSERT INTO beneficiaries (id, account_id, type, name, relationship, dob, ssn_last4, allocation_pct) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("ben-001a", "acc-001a", "primary", "David Chen", "spouse", "1963-07-22", "5544", 100.0),
            ("ben-001b", "acc-001a", "contingent", "Sarah Chen", "child", "1992-02-14", "9988", 50.0),
            ("ben-001c", "acc-001a", "contingent", "Michael Chen", "child", "1995-09-30", "7733", 50.0),
        ],
    )
    conn.executemany(
        "INSERT INTO investments (id, account_id, fund_ticker, fund_name, shares, current_value, target_allocation_pct) VALUES (?,?,?,?,?,?,?)",
        [
            ("inv-001a", "acc-001a", "VTSAX", "Vanguard Total Stock Market", 2150.5, 367500.20, 60.0),
            ("inv-001b", "acc-001a", "VBTLX", "Vanguard Total Bond Market", 18800.0, 184900.30, 30.0),
            ("inv-001c", "acc-001a", "VTIAX", "Vanguard Total International", 1830.0, 60000.00, 10.0),
            ("inv-001d", "acc-001b", "FXAIX", "Fidelity 500 Index", 920.0, 184250.00, 100.0),
        ],
    )
    conn.execute(
        "INSERT INTO contributions (id, account_id, contribution_pct, employer_match_pct, effective_date) VALUES (?,?,?,?,?)",
        ("con-001a", "acc-001a", 12.0, 5.0, "2024-01-01"),
    )
    conn.executemany(
        "INSERT INTO transactions (id, account_id, txn_date, txn_type, amount, fund_ticker, description) VALUES (?,?,?,?,?,?,?)",
        [
            ("txn-001a", "acc-001a", "2026-04-30", "contribution", 1850.00, "VTSAX", "Bi-weekly payroll contribution"),
            ("txn-001b", "acc-001a", "2026-04-30", "contribution", 770.83, "VTSAX", "Employer match"),
            ("txn-001c", "acc-001a", "2026-04-15", "contribution", 1850.00, "VTSAX", "Bi-weekly payroll contribution"),
            ("txn-001d", "acc-001a", "2026-03-31", "dividend", 1240.50, "VTSAX", "Q1 dividend reinvest"),
            ("txn-001e", "acc-001b", "2026-03-31", "dividend", 320.10, "FXAIX", "Q1 dividend reinvest"),
            ("txn-001f", "acc-001a", "2026-02-15", "fee", -25.00, None, "Annual administrative fee"),
        ],
    )
    conn.execute(
        "INSERT INTO tax_withholding (account_id, tax_year, federal_pct, state_code, state_pct) VALUES (?,?,?,?,?)",
        ("acc-001a", 2026, 20.0, "CA", 8.0),
    )
    conn.execute(
        "INSERT INTO bank_accounts (id, customer_id, nickname, routing_number_last4, account_number_last4, account_type, is_default, verified_at) VALUES (?,?,?,?,?,?,?,?)",
        ("bnk-001a", "demo-001", "Wells Fargo Checking", "0815", "4477", "checking", 1, "2023-06-12"),
    )
    conn.execute(
        "INSERT INTO documents (id, account_id, kind, period_start, period_end, file_path, generated_at) VALUES (?,?,?,?,?,?,?)",
        ("doc-001a", "acc-001a", "statement_quarterly", "2026-01-01", "2026-03-31", "documents/demo-001/2026-Q1.pdf", "2026-04-05"),
    )


def _seed_demo_002(conn):
    # Tyler: mid-career, has a loan, target allocations only partially funded.
    conn.executemany(
        "INSERT INTO accounts (id, customer_id, account_type, plan_name, balance, vested_balance, status, opened_date) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("acc-002a", "demo-002", "401k", "Bluebird Tech 401(k)", 178300.00, 142640.00, "active", "2014-06-01"),
            ("acc-002b", "demo-002", "ira_roth", "Personal Roth IRA", 42180.00, 42180.00, "active", "2018-04-15"),
        ],
    )
    conn.executemany(
        "INSERT INTO beneficiaries (id, account_id, type, name, relationship, dob, ssn_last4, allocation_pct) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("ben-002a", "acc-002a", "primary", "Maya Rodriguez", "spouse", "1991-12-08", "8765", 100.0),
        ],
    )
    conn.executemany(
        "INSERT INTO investments (id, account_id, fund_ticker, fund_name, shares, current_value, target_allocation_pct) VALUES (?,?,?,?,?,?,?)",
        [
            ("inv-002a", "acc-002a", "VTSAX", "Vanguard Total Stock Market", 720.0, 124810.00, 80.0),
            ("inv-002b", "acc-002a", "VBTLX", "Vanguard Total Bond Market", 5400.0, 53490.00, 20.0),
            ("inv-002c", "acc-002b", "VFIAX", "Vanguard 500 Index", 102.5, 42180.00, 100.0),
        ],
    )
    conn.execute(
        "INSERT INTO contributions (id, account_id, contribution_pct, employer_match_pct, effective_date) VALUES (?,?,?,?,?)",
        ("con-002a", "acc-002a", 8.0, 4.0, "2026-01-01"),
    )
    conn.execute(
        "INSERT INTO loans (id, account_id, principal, interest_rate, term_months, outstanding, status, next_payment_due) VALUES (?,?,?,?,?,?,?,?)",
        ("loan-002a", "acc-002a", 18000.00, 7.5, 60, 12450.30, "active", "2026-05-15"),
    )
    conn.executemany(
        "INSERT INTO transactions (id, account_id, txn_date, txn_type, amount, fund_ticker, description) VALUES (?,?,?,?,?,?,?)",
        [
            ("txn-002a", "acc-002a", "2026-04-30", "contribution", 615.38, "VTSAX", "Bi-weekly payroll contribution"),
            ("txn-002b", "acc-002a", "2026-04-15", "contribution", 615.38, "VTSAX", "Bi-weekly payroll contribution"),
            ("txn-002c", "acc-002a", "2026-03-31", "dividend", 412.30, "VTSAX", "Q1 dividend reinvest"),
        ],
    )
    conn.execute(
        "INSERT INTO bank_accounts (id, customer_id, nickname, routing_number_last4, account_number_last4, account_type, is_default, verified_at) VALUES (?,?,?,?,?,?,?,?)",
        ("bnk-002a", "demo-002", "Chase Checking", "1234", "9981", "checking", 1, "2022-11-04"),
    )


def _seed_demo_003(conn):
    # Nina: young, single account, NO beneficiary (so add-beneficiary demo has empty start state).
    conn.execute(
        "INSERT INTO accounts (id, customer_id, account_type, plan_name, balance, vested_balance, status, opened_date) VALUES (?,?,?,?,?,?,?,?)",
        ("acc-003a", "demo-003", "ira_roth", "Personal Roth IRA", 8920.50, 8920.50, "active", "2023-02-20"),
    )
    conn.execute(
        "INSERT INTO investments (id, account_id, fund_ticker, fund_name, shares, current_value, target_allocation_pct) VALUES (?,?,?,?,?,?,?)",
        ("inv-003a", "acc-003a", "VTSAX", "Vanguard Total Stock Market", 51.0, 8920.50, 100.0),
    )
    conn.execute(
        "INSERT INTO contributions (id, account_id, contribution_pct, employer_match_pct, effective_date) VALUES (?,?,?,?,?)",
        ("con-003a", "acc-003a", 0.0, 0.0, "2023-02-20"),
    )
    conn.executemany(
        "INSERT INTO transactions (id, account_id, txn_date, txn_type, amount, fund_ticker, description) VALUES (?,?,?,?,?,?,?)",
        [
            ("txn-003a", "acc-003a", "2026-04-15", "contribution", 500.00, "VTSAX", "Personal contribution"),
            ("txn-003b", "acc-003a", "2026-03-15", "contribution", 500.00, "VTSAX", "Personal contribution"),
        ],
    )


def main() -> int:
    reset_db()
    conn = get_db()
    for c in DEMO_CUSTOMERS:
        _insert_customer(conn, c)
    _seed_demo_001(conn)
    _seed_demo_002(conn)
    _seed_demo_003(conn)
    conn.commit()
    print("Seeded customers:")
    for c in DEMO_CUSTOMERS:
        print(f"  {c['id']:10}  {c['first_name']} {c['last_name']:12}  DOB {c['dob']}  SSN-last4 {c['ssn_last4']}")
    print('OTP for verification: 123456')
    return 0


if __name__ == "__main__":
    sys.exit(main())
