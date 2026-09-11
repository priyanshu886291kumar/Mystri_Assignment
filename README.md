# ClearLedger — Invoice & Payment Register
> **Mystri Practical Assessment — Track A: Product Engineering**  
> *Candidate:* **Priyanshu Kumar** &nbsp;|&nbsp; *Status:* **All 6 Defects Repaired & 25 Tests Passing** &nbsp;|&nbsp; *Runtime:* **Python 3.10+ (Zero Dependencies)**

---

## Executive Summary

**ClearLedger** is a local invoice and payment register application built with Python's standard library and vanilla web technologies.

This repository contains the complete repair, verification suite, and collection-prioritization enhancements for Track A:
- **All 6 deliberately seeded defects** have been identified, repaired, and verified with dedicated regression tests.
- **The owner's existing register fixture** (`fixtures/existing-register.sqlite3`) is 100% preserved and verified against `fixtures/expected-records.json`.
- **Valuable product improvements** were added: dynamic customer-level filtering, due-date & balance sorting, and line-by-line CSV import error diagnostics.
- **25 comprehensive automated tests** pass in ~0.5s with zero external dependencies.

---

## Quick Run & Verification

```bash
# 1. Run the full test suite (25 tests covering regressions, edge cases, and fixtures)
python -m unittest discover -s tests -v

# 2. Reset the demo database (starting fresh with 6 demo invoices)
python app.py reset-demo

# 3. Restore the owner's existing register (9 invoices, 5 payments, 1 unmatched payment)
python restore_fixture.py --replace

# 4. Start the local server (default: http://127.0.0.1:8787)
python app.py
```
*Open [http://127.0.0.1:8787](http://127.0.0.1:8787) in your browser.*

---

## Defect Repairs & Technical Architecture

| # | Component | Seeded Defect | Root Cause & Resolution | Verification |
|---|---|---|---|---|
| **1** | `ledger/importing.py` | CSV import batch failure on single invalid row | Pre-loop list comprehension aborted the whole file on the first error. Converted to row-by-row normalization inside the transaction loop, recording CSV line numbers and rejection reasons while importing valid rows. | `DefectRegressionTests.test_defect_1_mixed_validity_csv_processes_valid_rows` |
| **2** | `ledger/storage.py` | Duplicate invoice insertion & missing idempotency | `insert_invoice` performed unconditional `INSERT`. Added `(customer_id, invoice_number)` key checking: skips identical records idempotently and rejects conflicting details. | `DefectRegressionTests.test_defect_2_invoice_deduplication_and_conflict_rejection` |
| **3** | `ledger/matching.py` | Erroneous payment matching by amount | `find_invoice` matched payments by `amount` across arbitrary customers. Removed amount matching; payments now attach **only** when both `customer_id` and `invoice_number` match. Unresolved payments stay unmatched (`invoice_id = NULL`). | `DefectRegressionTests.test_defect_3_payment_matching_strictly_by_customer_and_invoice` |
| **4** | `ledger/reporting.py` | Inverted `open` status filter | Query logic mapped `{'open': 'paid'}`. Fixed mapping so `status=open` returns positive balance invoices ($>0$) and `status=paid` returns paid/overpaid invoices ($\le 0$). | `DefectRegressionTests.test_defect_4_status_filtering_open_and_paid` |
| **5** | `ledger/reporting.py` | Float truncation & export corruption | Integer truncation `int(val * 100) / 100` turned `19.99` into `19.98` and truncated negative balances. Enforced exact decimal formatting (`f"{val:.2f}"`) preserving cent precision on all values and overpayments. | `DefectRegressionTests.test_defect_5_csv_export_money_precision_and_overpayment` |
| **6** | `web/app.js` | False UI success on failed/partial imports | `submitImport` ignored response status codes and payloads. Added JSON response parsing, displaying exact counts (imported/skipped/rejected) and an actionable line-by-line error list. | `DefectRegressionTests.test_defect_6_import_result_structure_and_error_details` |

---

## Useful Product Improvements Added

1. **Customer-Level Filtering**:
   - Filter invoice register by customer (`HARBOR`, `MAPLE`, `NORTH`, or `All Customers`) on both the REST API (`/api/invoices?customer_id=...`) and the frontend UI.
2. **Due Date & Balance Sorting**:
   - Sort invoices by `Due Date (Earliest / Latest)` or `Balance (Highest / Lowest)` to help the owner prioritize collections during busy weeks.
3. **Interactive CSV Import Diagnostics**:
   - Real-time visual feedback with line numbers and reasons for rejected rows, styled status pills (`open` vs `paid`), and clear feedback banners.

---

## Fixture Preservation & Database Integrity

The owner's database fixture (`fixtures/existing-register.sqlite3`) contains:
- **3 Customers**: `HARBOR`, `MAPLE`, `NORTH`
- **9 Invoices**: 7 open, 2 paid
- **5 Payments**: 4 attached, 1 unmatched payment (`KEEP-U1` for `MAPLE / WAIT-900` of INR 33.33)
- **Total Outstanding**: **INR 3,698.19**

[`tests/test_fixture_preservation.py`](tests/test_fixture_preservation.py) verifies that all original records match `fixtures/expected-records.json`, and that new imports persist across database restarts without altering historical records.

---

## Repository Structure

```text
Mystri_Assignment/
├── app.py                      # Application entry point (serve & reset-demo)
├── restore_fixture.py          # Restores the owner's existing SQLite fixture
├── BUSINESS_RULES.md           # Public business rules & API specification
├── HANDOVER.md                 # Candidate handover notes, evidence, and tool judgment
├── README.md                   # Project overview & documentation
│
├── ledger/                     # Core backend domain logic
│   ├── http_app.py             # HTTP request dispatcher & route handlers
│   ├── importing.py            # CSV parsing, row-by-row isolation & error aggregation
│   ├── matching.py             # Strict customer & invoice payment matching
│   ├── reporting.py            # Overview metrics, status/customer filtering, CSV export
│   ├── storage.py              # SQLite connection, schema, seeding & idempotent insertion
│   └── validation.py           # Header validation, data sanitization & date/amount checks
│
├── web/                        # Lightweight vanilla frontend
│   ├── index.html              # Clean semantic markup with metrics & filter controls
│   ├── style.css               # Responsive stylesheet with status badges & alerts
│   └── app.js                  # Asynchronous client with rich import error diagnostics
│
├── fixtures/                   # Owner's existing database fixture & expected baseline
│   ├── README.md               # Fixture specifications & starting totals
│   ├── existing-register.sqlite3 # Synthetic SQLite database to preserve
│   └── expected-records.json   # Ground-truth record reference
│
├── samples/                    # Sample CSV files for testing imports
│   ├── invoices-mixed.csv      # CSV with valid and invalid rows
│   ├── invoices-new.csv        # Valid new invoice records
│   ├── payments.csv            # Valid new payment records
│   └── wrong-header.csv        # Invalid CSV header
│
└── tests/                      # Automated test suite (25 tests)
    ├── test_defects.py         # Regression tests for all 6 seeded defects
    ├── test_fixture_preservation.py # Database preservation & restart persistence tests
    ├── test_edge_cases.py      # BOM, whitespace, 10M amount boundaries & overpayments
    ├── test_improvements.py    # Customer filtering and due date/balance sorting tests
    └── test_smoke.py           # Smoke checks
```

---

## Detailed Handover

For full details on the testing evidence, changed-input verification, and AI/tool decisions, please refer to [**HANDOVER.md**](HANDOVER.md).
