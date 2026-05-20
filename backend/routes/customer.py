"""Customer endpoint — returns the demo customer + their account summary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import DEFAULT_CUSTOMER_ID, get_repo
from db.repository import Repository

router = APIRouter()


@router.get("/customer")
def get_customer(repo: Repository = Depends(get_repo)) -> dict:
    c = repo.get_customer(DEFAULT_CUSTOMER_ID)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    summary = repo.get_balance_summary(DEFAULT_CUSTOMER_ID)
    return {"customer": dict(c), "balance": summary}
