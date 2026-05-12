"""Repository — only place mutating SQL lives.

Every mutation writes an `audit_log` row and (where appropriate) a `requests` row
inside the same transaction, using a caller-supplied idempotency key so
re-running the agent graph doesn't double-write.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class WriteResult:
    request_id: str
    audit_id: str
    duplicate: bool = False  # True if idempotency key already existed


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ---------- read helpers ----------

    def list_customers(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT id, first_name, last_name FROM customers ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None

    def get_accounts(self, customer_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM accounts WHERE customer_id = ? ORDER BY opened_date", (customer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_balance_summary(self, customer_id: str) -> dict[str, Any]:
        accounts = self.get_accounts(customer_id)
        total = sum(a["balance"] for a in accounts)
        vested = sum(a["vested_balance"] for a in accounts)
        return {
            "total_balance": total,
            "vested_balance": vested,
            "accounts": [
                {
                    "id": a["id"],
                    "type": a["account_type"],
                    "plan_name": a["plan_name"],
                    "balance": a["balance"],
                    "vested_balance": a["vested_balance"],
                }
                for a in accounts
            ],
        }

    def get_transactions(self, customer_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT t.* FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE a.customer_id = ?
            ORDER BY t.txn_date DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_beneficiaries(self, customer_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT b.*, a.plan_name FROM beneficiaries b
            JOIN accounts a ON a.id = b.account_id
            WHERE a.customer_id = ?
            ORDER BY a.id, b.type, b.name
            """,
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_contribution(self, account_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM contributions WHERE account_id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return dict(row) if row else None

    def list_requests(self, customer_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM requests WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- identity ----------

    def verify_identity(self, customer_id: str, dob: str, ssn_last4: str) -> bool:
        c = self.get_customer(customer_id)
        if not c:
            return False
        return c["dob"] == dob and c["ssn_last4"] == ssn_last4

    # ---------- mutating helpers ----------

    def _write_audit_and_request(
        self,
        cur: sqlite3.Cursor,
        *,
        customer_id: str,
        thread_id: str | None,
        action: str,
        request_type: str,
        payload: dict[str, Any],
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        idempotency_key: str,
        routing_target: str = "self_service",
        request_status: str = "completed",
    ) -> WriteResult:
        existing = cur.execute(
            "SELECT id FROM requests WHERE client_request_id = ?", (idempotency_key,)
        ).fetchone()
        if existing:
            audit = cur.execute(
                "SELECT id FROM audit_log WHERE customer_id = ? AND action = ? ORDER BY occurred_at DESC LIMIT 1",
                (customer_id, action),
            ).fetchone()
            return WriteResult(request_id=existing["id"], audit_id=audit["id"] if audit else "", duplicate=True)

        request_id = _new_id("req")
        audit_id = _new_id("aud")
        now = _now()
        resolved_at = now if request_status in ("completed", "rejected") else None

        cur.execute(
            """
            INSERT INTO requests (id, client_request_id, customer_id, type, status,
                                  payload_json, routing_target, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (request_id, idempotency_key, customer_id, request_type, request_status,
             json.dumps(payload), routing_target, now, resolved_at),
        )
        cur.execute(
            """
            INSERT INTO audit_log (id, customer_id, thread_id, action, before_json, after_json, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, customer_id, thread_id, action,
             json.dumps(before) if before is not None else None,
             json.dumps(after) if after is not None else None,
             now),
        )
        return WriteResult(request_id=request_id, audit_id=audit_id, duplicate=False)

    def update_address(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        new_address: dict[str, str],
        idempotency_key: str,
    ) -> WriteResult:
        before = self.get_customer(customer_id)
        if not before:
            raise ValueError(f"Unknown customer {customer_id}")
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                UPDATE customers SET
                    address_line1 = ?, address_line2 = ?, address_city = ?,
                    address_state = ?, address_postal = ?, address_country = ?
                WHERE id = ?
                """,
                (
                    new_address["address_line1"],
                    new_address.get("address_line2"),
                    new_address["address_city"],
                    new_address["address_state"],
                    new_address["address_postal"],
                    new_address.get("address_country", "US"),
                    customer_id,
                ),
            )
            after_addr = {k: new_address.get(k) for k in (
                "address_line1", "address_line2", "address_city",
                "address_state", "address_postal", "address_country")}
            before_addr = {k: before.get(k) for k in after_addr}
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="customer.address.update",
                request_type="address_change",
                payload=new_address,
                before=before_addr,
                after=after_addr,
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def update_phone(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        new_phone: str,
        idempotency_key: str,
    ) -> WriteResult:
        before = self.get_customer(customer_id)
        if not before:
            raise ValueError(f"Unknown customer {customer_id}")
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute("UPDATE customers SET phone = ? WHERE id = ?", (new_phone, customer_id))
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="customer.phone.update",
                request_type="change_phone",
                payload={"phone": new_phone},
                before={"phone": before["phone"]},
                after={"phone": new_phone},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def add_beneficiary(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        beneficiary: dict[str, Any],
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            existing = cur.execute(
                "SELECT id, customer_id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if not existing or existing["customer_id"] != customer_id:
                raise ValueError(f"Account {account_id} does not belong to {customer_id}")

            new_id = _new_id("ben")
            cur.execute(
                """
                INSERT INTO beneficiaries (id, account_id, type, name, relationship, dob, ssn_last4, allocation_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    account_id,
                    beneficiary["type"],
                    beneficiary["name"],
                    beneficiary["relationship"],
                    beneficiary["dob"],
                    beneficiary["ssn_last4"],
                    float(beneficiary["allocation_pct"]),
                ),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="beneficiary.add",
                request_type="add_beneficiary",
                payload={"account_id": account_id, **beneficiary},
                before=None,
                after={"id": new_id, **beneficiary, "account_id": account_id},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def update_contribution(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        new_pct: float,
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            account = cur.execute(
                "SELECT customer_id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if not account or account["customer_id"] != customer_id:
                raise ValueError(f"Account {account_id} does not belong to {customer_id}")
            before_row = cur.execute(
                "SELECT contribution_pct FROM contributions WHERE account_id = ?", (account_id,)
            ).fetchone()
            before_pct = before_row["contribution_pct"] if before_row else 0.0

            cur.execute(
                """
                INSERT INTO contributions (id, account_id, contribution_pct, employer_match_pct, effective_date)
                VALUES (?, ?, ?, COALESCE((SELECT employer_match_pct FROM contributions WHERE account_id = ?), 0), ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    contribution_pct = excluded.contribution_pct,
                    effective_date   = excluded.effective_date
                """,
                (_new_id("con"), account_id, new_pct, account_id, _now()[:10]),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="contribution.update",
                request_type="change_contribution",
                payload={"account_id": account_id, "contribution_pct": new_pct},
                before={"contribution_pct": before_pct},
                after={"contribution_pct": new_pct},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise
