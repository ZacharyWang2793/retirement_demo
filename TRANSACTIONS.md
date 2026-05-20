# Supported Transactions

The Meridian Retirement agent facilitates **21 distinct transactions** across six retirement-account domains. Each transaction has a real step plan (`verify → otp → collect → confirm → persist → inform`) — there are no "not implemented" stubs.

Example phrases in *italics* are recognized by the regex prefilter; anything else falls through to the Azure-hosted LLM, which picks the matching intent via its `start_workflow` tool.

---

## Profile & contact (4)

| Intent | What happens | Example phrasing |
|---|---|---|
| **Change address** | Verify → OTP → address form → confirm → persists to `customers` + writes audit row | *"I want to change my address"* |
| **Change phone** | Verify → OTP → phone form → confirm | *"update my phone number"* |
| **Change email** | Verify → OTP → email form → confirm (updates `customers` and `users`) | *"change my email"* |
| **Change legal name** | Verify → OTP → form with mock document upload → updates `customers` and writes a `documents` row of kind `name_change_*` | *"change my legal name"* |

## Beneficiaries (2)

| Intent | What happens | Example |
|---|---|---|
| **Add a beneficiary** | Verify → OTP → form (pick account, name, relationship, allocation) → confirm | *"add a beneficiary"* |
| **Update / remove a beneficiary** | Verify → OTP → picker → branches via `skip_if` into edit form OR removal confirm | *"update my beneficiaries"*, *"remove a beneficiary"* |

## Read-only & status (4)

| Intent | What happens | Example |
|---|---|---|
| **Check balance** | Hero card with portfolio total + vested + pastel-tinted account grid | *"what's my balance?"* |
| **View transactions** | Last 20 entries with filter chips (All / Contributions / Distributions / Dividends / Fees) | *"show my transactions"* |
| **Check request status** | List of pending / completed / cancelled requests with status pills | *"what's the status of my requests?"* |
| **Cancel a pending request** | Verify → OTP → pick → confirm → flips status to `cancelled`, audit-logged | *"cancel my request"* |

## Investments & contributions (3)

| Intent | What happens | Example |
|---|---|---|
| **Change contribution amount** | Pick 401(k) / Roth 401(k) account, slider for new % | *"change my contribution"* |
| **Change investment allocation** | Per-fund sliders, must-sum-to-100 validator, writes `investments.target_allocation_pct` | *"change my allocation"* |
| **Rebalance portfolio** | Computes drift, shows per-fund trade plan, writes a pending `rebalance` request | *"rebalance my portfolio"* |

## Distributions & withdrawals (6)

| Intent | What happens | Example |
|---|---|---|
| **Take RMD** | Computes required amount from age + balance, pick method (bank / check), tax withholding | *"take my RMD"* |
| **Qualified distribution** | Pick account, amount, method, federal withholding → writes a `distributions` row | *"qualified distribution"* |
| **Hardship withdrawal** ⚠ | Reason + mock document upload → specialist-routed; pending `requests` row with `routing_target='specialist_review'` | *"hardship withdrawal"* |
| **Roll over OUT** ⚠ | Destination plan + amount + direct/indirect method → specialist-routed | *"roll over my 401k to another plan"* |
| **Roll over IN** ⚠ | Source plan info → specialist-routed (no identity verification required) | *"roll over funds in from another plan"* |
| **QDRO** ⚠ | Case # + court + mock order upload → specialist-routed | *"QDRO"* |

⚠ = compliance-heavy; the flow ends with a `SpecialistRoutingCard` and a `requests` row that becomes visible later via *check request status*.

## Tax & banking (2)

| Intent | What happens | Example |
|---|---|---|
| **Update tax withholding** | Pick account + year, federal/state % sliders → upserts `tax_withholding` | *"update my federal tax withholding"* |
| **Update direct deposit** | Bank-account form → mocked micro-deposit verification (0.12 / 0.34) → activates + can set default | *"update direct deposit"* |

---

## Testing credentials

All three seeded demo customers share the same **OTP code: `123456`**.

| ID | Name | DOB | SSN last-4 |
|---|---|---|---|
| `demo-001` | Margaret Chen | 1965-04-12 | 6789 |
| `demo-002` | Tyler Rodriguez | 1989-08-23 | 4321 |
| `demo-003` | Nina Patel | 1996-11-04 | 1122 |

Each customer is pre-seeded with one pending `change_phone` request so the *cancel request* flow has something to act on.
