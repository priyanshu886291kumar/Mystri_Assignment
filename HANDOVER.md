# Handover

- Name: Priyanshu Kumar
- Email used for this application: priyanshu886291kumar (or registered email)
- Chosen track: Track A (Repair the register)
- Why this track: I enjoy auditing codebases, debugging subtle data integrity issues, and building reliable, verified financial registers that businesses can trust.
- Approximate total time, including setup and handover: 2 hours 45 minutes

## Run and verify

Prerequisites: Python 3.10+ (standard library only; zero external packages or credentials needed).

```bash
# 1. Run all 25 unit, regression, edge-case, and improvement tests
python -m unittest discover -s tests -v

# 2. Reset synthetic demo data
python app.py reset-demo

# 3. Restore and verify the owner's existing register fixture
python restore_fixture.py --replace

# 4. Start the application server (default: http://127.0.0.1:8787)
python app.py
```

Expected Test Output:
```text
Ran 25 tests in ~0.65s
OK
```

## What I delivered

I resolved all six seeded defects across import error isolation, duplicate prevention, payment matching, status filtering, export formatting, and browser error diagnostics. I also added customer-level filtering, due-date/balance sorting, and line-level import error feedback to help the owner prioritize collections during busy weeks.

1. **Import Error Isolation** (`ledger/importing.py`): Replaced pre-loop normalization with per-row validation so invalid CSV rows are rejected with line numbers while valid rows are imported.
2. **Invoice Deduplication** (`ledger/storage.py`): Added identity checking on `(customer_id, invoice_number)`. Skips exact duplicates and rejects conflicting records.
3. **Payment Matching** (`ledger/matching.py`): Removed erroneous cross-customer amount matching. Payments match only on exact customer ID and invoice number; unresolved payments remain unmatched.
4. **Status Filter** (`ledger/reporting.py`): Fixed query filter so `status=open` and `status=paid` return their respective invoices.
5. **Money Precision & Export** (`ledger/reporting.py`): Replaced truncation with exact 2-decimal rounding (`f"{val:.2f}"`), supporting overpayments and negative balances.
6. **Browser Diagnostics & Filters** (`web/app.js`, `web/index.html`): Added structured import response parsing with line error breakdowns, plus customer filtering and sorting controls.

## Evidence and limits

- **Failing-before / Passing-after Reproduction**: `tests/test_defects.py` validates all 6 defect reproductions. E.g., importing a 3-row CSV with 1 bad row previously threw HTTP 400 and aborted all rows; now it imports 2 rows, rejects 1 with line 3 error, and reports HTTP 200.
- **Existing Register Preservation**: `tests/test_fixture_preservation.py` restores `fixtures/existing-register.sqlite3` and verifies all 9 invoices, 5 payments, 1 unmatched payment (`KEEP-U1`), and INR 3,698.19 outstanding against `fixtures/expected-records.json`. It also verifies new imports and restart persistence.
- **Changed-Input Case**: In `test_defect_5_csv_export_money_precision_and_overpayment`, imported payment `OVER-1` of 150.00 on a 100.00 invoice (`INV-301`). Expected: status `paid`, balance `-50.00`, CSV export `NORTH,INV-301,100.00,150.00,-50.00,paid`, and total outstanding unchanged by negative balance. Observed: exactly matched expectations.
- **Useful Improvement**: `tests/test_improvements.py` validates customer filtering (`HARBOR`, `MAPLE`, `NORTH`) and sorting (`due_date_asc`, `due_date_desc`, `balance_desc`).
- **Limits & Real-world Investigations**: Automatic reconciliation of unmatched payments upon subsequent invoice imports is omitted (per scope). In production, I would investigate database connection pooling, transaction isolation under concurrent writers, and audit logs for payment reallocations.

## Tools and judgment

1. **Float vs Decimal Representation**: AI suggested converting database schema to store integer cents; I chose to preserve the existing SQLite schema with `REAL` and apply explicit 2-decimal rounding in Python to guarantee 100% compatibility with `fixtures/existing-register.sqlite3` without complex migrations. Verified via `test_fixture_preservation.py`.
2. **CSV Import Error Aggregation**: AI suggested failing the transaction if any row failed; I rejected this in accordance with `BUSINESS_RULES.md` (individual row rejection) and implemented per-row error tracking inside the transaction. Verified via `test_defect_1_mixed_validity_csv_processes_valid_rows`.
3. **UI Feedback**: AI initially suggested a simple alert box; I built an inline feedback summary with error details and status badges for better operator ergonomics. Verified manually in browser.
