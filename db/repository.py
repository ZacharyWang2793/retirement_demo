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


def _mask(s: str) -> str:
    digits = [c for c in s if c.isdigit()]
    if len(digits) <= 4:
        return s
    return "*" * (len(digits) - 4) + "".join(digits[-4:])


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

    def list_documents(self, customer_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.*, a.plan_name
              FROM documents d
              JOIN accounts a ON a.id = d.account_id
             WHERE a.customer_id = ?
             ORDER BY d.generated_at DESC
            """,
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_investments(self, account_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM investments WHERE account_id = ? ORDER BY target_allocation_pct DESC",
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_bank_accounts(self, customer_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM bank_accounts WHERE customer_id = ? ORDER BY is_default DESC, nickname",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tax_withholding(self, account_id: str, tax_year: int | None = None) -> dict[str, Any] | None:
        if tax_year is None:
            row = self.conn.execute(
                "SELECT * FROM tax_withholding WHERE account_id = ? ORDER BY tax_year DESC LIMIT 1",
                (account_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM tax_withholding WHERE account_id = ? AND tax_year = ?",
                (account_id, tax_year),
            ).fetchone()
        return dict(row) if row else None

    # ---------- request lifecycle ----------

    def cancel_request(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        request_id: str,
        idempotency_key: str,
    ) -> WriteResult:
        """Cancel a pending request. Idempotent: re-cancelling a cancelled request returns duplicate=True."""
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            target = cur.execute(
                "SELECT id, customer_id, status FROM requests WHERE id = ?", (request_id,)
            ).fetchone()
            if not target:
                raise ValueError(f"Unknown request {request_id}")
            if target["customer_id"] != customer_id:
                raise ValueError(f"Request {request_id} does not belong to {customer_id}")
            if target["status"] != "pending":
                raise ValueError(f"Request {request_id} is not cancellable (status={target['status']})")
            cur.execute(
                "UPDATE requests SET status = 'cancelled', resolved_at = ? WHERE id = ?",
                (_now(), request_id),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="request.cancel",
                request_type="cancel_request",
                payload={"cancelled_request_id": request_id},
                before={"status": "pending"},
                after={"status": "cancelled"},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def route_to_specialist(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        request_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> WriteResult:
        """Write a pending `requests` row routed to specialist_review. No domain mutation."""
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action=f"specialist.{request_type}.intake",
                request_type=request_type,
                payload=payload,
                before=None,
                after=payload,
                idempotency_key=idempotency_key,
                routing_target="specialist_review",
                request_status="pending",
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # ---------- contact updates ----------

    def update_email(
        self, *, customer_id: str, thread_id: str | None, new_email: str, idempotency_key: str,
    ) -> WriteResult:
        before = self.get_customer(customer_id)
        if not before:
            raise ValueError(f"Unknown customer {customer_id}")
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute("UPDATE customers SET email = ? WHERE id = ?", (new_email, customer_id))
            cur.execute(
                "UPDATE users SET email = ? WHERE customer_id = ?", (new_email, customer_id)
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="customer.email.update",
                request_type="change_email",
                payload={"email": new_email},
                before={"email": before["email"]},
                after={"email": new_email},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def update_name(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        first_name: str,
        last_name: str,
        doc_kind: str,
        doc_file_name: str,
        idempotency_key: str,
    ) -> WriteResult:
        before = self.get_customer(customer_id)
        if not before:
            raise ValueError(f"Unknown customer {customer_id}")
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                "UPDATE customers SET first_name = ?, last_name = ? WHERE id = ?",
                (first_name, last_name, customer_id),
            )
            # Persist the mocked supporting-document upload under the customer's first account
            first_acct = cur.execute(
                "SELECT id FROM accounts WHERE customer_id = ? ORDER BY opened_date LIMIT 1",
                (customer_id,),
            ).fetchone()
            if first_acct:
                cur.execute(
                    """
                    INSERT INTO documents (id, account_id, kind, period_start, period_end, file_path, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _new_id("doc"),
                        first_acct["id"],
                        f"name_change_{doc_kind}",
                        _now()[:10],
                        _now()[:10],
                        f"documents/{customer_id}/name-change/{doc_file_name}",
                        _now(),
                    ),
                )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="customer.name.update",
                request_type="change_name",
                payload={"first_name": first_name, "last_name": last_name, "doc_kind": doc_kind},
                before={"first_name": before["first_name"], "last_name": before["last_name"]},
                after={"first_name": first_name, "last_name": last_name},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # ---------- beneficiary edit / remove ----------

    def update_beneficiary(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        beneficiary_id: str,
        updates: dict[str, Any],
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            before_row = cur.execute(
                """
                SELECT b.*, a.customer_id AS owner_id
                  FROM beneficiaries b
                  JOIN accounts a ON a.id = b.account_id
                 WHERE b.id = ?
                """,
                (beneficiary_id,),
            ).fetchone()
            if not before_row or before_row["owner_id"] != customer_id:
                raise ValueError(f"Beneficiary {beneficiary_id} does not belong to {customer_id}")
            before = dict(before_row)
            allowed = {"type", "name", "relationship", "dob", "ssn_last4", "allocation_pct"}
            sets = {k: v for k, v in updates.items() if k in allowed}
            if not sets:
                raise ValueError("No supported fields provided in update")
            assignments = ", ".join(f"{k} = ?" for k in sets)
            cur.execute(
                f"UPDATE beneficiaries SET {assignments} WHERE id = ?",
                (*sets.values(), beneficiary_id),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="beneficiary.update",
                request_type="update_beneficiary",
                payload={"beneficiary_id": beneficiary_id, **sets},
                before={k: before.get(k) for k in sets},
                after=sets,
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def remove_beneficiary(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        beneficiary_id: str,
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            before_row = cur.execute(
                """
                SELECT b.*, a.customer_id AS owner_id
                  FROM beneficiaries b
                  JOIN accounts a ON a.id = b.account_id
                 WHERE b.id = ?
                """,
                (beneficiary_id,),
            ).fetchone()
            if not before_row or before_row["owner_id"] != customer_id:
                raise ValueError(f"Beneficiary {beneficiary_id} does not belong to {customer_id}")
            before = dict(before_row)
            cur.execute("DELETE FROM beneficiaries WHERE id = ?", (beneficiary_id,))
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="beneficiary.remove",
                request_type="remove_beneficiary",
                payload={"beneficiary_id": beneficiary_id},
                before={k: before.get(k) for k in ("name", "relationship", "allocation_pct", "account_id")},
                after=None,
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # ---------- tax / banking ----------

    def update_tax_withholding(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        tax_year: int,
        federal_pct: float,
        state_code: str,
        state_pct: float,
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            owner = cur.execute(
                "SELECT customer_id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if not owner or owner["customer_id"] != customer_id:
                raise ValueError(f"Account {account_id} does not belong to {customer_id}")
            before_row = cur.execute(
                "SELECT * FROM tax_withholding WHERE account_id = ? AND tax_year = ?",
                (account_id, tax_year),
            ).fetchone()
            cur.execute(
                """
                INSERT INTO tax_withholding (account_id, tax_year, federal_pct, state_code, state_pct)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id, tax_year) DO UPDATE SET
                    federal_pct = excluded.federal_pct,
                    state_code  = excluded.state_code,
                    state_pct   = excluded.state_pct
                """,
                (account_id, tax_year, federal_pct, state_code, state_pct),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="tax_withholding.update",
                request_type="update_tax_withholding",
                payload={
                    "account_id": account_id, "tax_year": tax_year,
                    "federal_pct": federal_pct, "state_code": state_code, "state_pct": state_pct,
                },
                before=dict(before_row) if before_row else None,
                after={"federal_pct": federal_pct, "state_code": state_code, "state_pct": state_pct},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def add_bank_account(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        nickname: str,
        routing_last4: str,
        account_last4: str,
        account_type: str,
        set_default: bool,
        idempotency_key: str,
    ) -> tuple[WriteResult, str]:
        """Insert a new bank_accounts row (unverified). Returns (WriteResult, bank_id)."""
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            bank_id = _new_id("bnk")
            cur.execute(
                """
                INSERT INTO bank_accounts (id, customer_id, nickname, routing_number_last4,
                                            account_number_last4, account_type, is_default, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (bank_id, customer_id, nickname, routing_last4, account_last4, account_type),
            )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="bank_account.add",
                request_type="add_bank_account",
                payload={
                    "nickname": nickname, "routing_last4": routing_last4,
                    "account_last4": account_last4, "account_type": account_type,
                    "set_default_after_verify": bool(set_default),
                },
                before=None,
                after={"id": bank_id, "nickname": nickname, "account_last4": account_last4},
                idempotency_key=idempotency_key,
                request_status="pending",
            )
            self.conn.commit()
            return result, bank_id
        except Exception:
            self.conn.rollback()
            raise

    def verify_bank_with_microdeposits(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        bank_account_id: str,
        set_default: bool,
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            row = cur.execute(
                "SELECT customer_id FROM bank_accounts WHERE id = ?", (bank_account_id,)
            ).fetchone()
            if not row or row["customer_id"] != customer_id:
                raise ValueError(f"Bank {bank_account_id} does not belong to {customer_id}")
            cur.execute(
                "UPDATE bank_accounts SET verified_at = ? WHERE id = ?",
                (_now(), bank_account_id),
            )
            if set_default:
                cur.execute(
                    "UPDATE bank_accounts SET is_default = 0 WHERE customer_id = ?",
                    (customer_id,),
                )
                cur.execute(
                    "UPDATE bank_accounts SET is_default = 1 WHERE id = ?",
                    (bank_account_id,),
                )
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="bank_account.verify",
                request_type="verify_bank",
                payload={"bank_account_id": bank_account_id, "set_default": bool(set_default)},
                before={"verified": False},
                after={"verified": True, "is_default": bool(set_default)},
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # ---------- allocation / rebalance ----------

    def update_allocation(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        allocations: list[dict[str, Any]],  # [{ticker, target_pct}]
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            owner = cur.execute(
                "SELECT customer_id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if not owner or owner["customer_id"] != customer_id:
                raise ValueError(f"Account {account_id} does not belong to {customer_id}")
            before_invs = cur.execute(
                "SELECT fund_ticker, target_allocation_pct FROM investments WHERE account_id = ?",
                (account_id,),
            ).fetchall()
            before = {r["fund_ticker"]: r["target_allocation_pct"] for r in before_invs}
            after = {}
            for a in allocations:
                cur.execute(
                    "UPDATE investments SET target_allocation_pct = ? WHERE account_id = ? AND fund_ticker = ?",
                    (a["target_pct"], account_id, a["ticker"]),
                )
                after[a["ticker"]] = a["target_pct"]
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="investments.allocation.update",
                request_type="change_allocation",
                payload={"account_id": account_id, "allocations": allocations},
                before=before,
                after=after,
                idempotency_key=idempotency_key,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def request_rebalance(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        plan: list[dict[str, Any]],
        idempotency_key: str,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action="investments.rebalance.request",
                request_type="rebalance",
                payload={"account_id": account_id, "plan": plan},
                before=None,
                after={"account_id": account_id, "trade_count": len(plan)},
                idempotency_key=idempotency_key,
                request_status="pending",
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # ---------- distributions ----------

    def create_distribution(
        self,
        *,
        customer_id: str,
        thread_id: str | None,
        account_id: str,
        kind: str,  # rmd | hardship | qualified | rollover_out
        amount: float,
        idempotency_key: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> WriteResult:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            owner = cur.execute(
                "SELECT customer_id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if not owner or owner["customer_id"] != customer_id:
                raise ValueError(f"Account {account_id} does not belong to {customer_id}")
            dist_id = _new_id("dst")
            cur.execute(
                """
                INSERT INTO distributions (id, account_id, type, amount, status, requested_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (dist_id, account_id, kind, amount, _now()),
            )
            payload = {"account_id": account_id, "type": kind, "amount": amount}
            if extra_payload:
                payload.update(extra_payload)
            result = self._write_audit_and_request(
                cur,
                customer_id=customer_id,
                thread_id=thread_id,
                action=f"distribution.{kind}.request",
                request_type=f"distribution_{kind}",
                payload=payload,
                before=None,
                after={"distribution_id": dist_id, "amount": amount, "type": kind},
                idempotency_key=idempotency_key,
                request_status="pending",
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
