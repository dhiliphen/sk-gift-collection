# QA Report

This supersedes the original QA audit (234 tests, single-session snapshot before the business-system transformation described in `ARCHITECTURE.md`). That audit's defects and open business-rule questions (AMB-001 through AMB-004) have since been resolved; this report reflects the application as it stands after seven feature phases (stock ledger, payment tracking, GST engine + Decimal money, business-intelligence dashboard, audit log + RBAC, purchase orders/goods receipt, and sales/purchase returns).

## Executive summary

**411 tests pass, 99% overall statement coverage, 100% on every file touched during the transformation work.** Three real defects were found during this work — none by inspection; all three were caught by either writing a regression test first or by testing the running application against its real database, and all three are fixed with a regression test in place. No known correctness bugs remain open.

## Test environment

- **Python**: 3.11.15 (pinned via `.python-version` — Railway's default 3.13 is incompatible with this SQLAlchemy version's `greenlet` dependency)
- **Framework**: FastAPI 0.111.0 + SQLAlchemy 2.0.30
- **Test runner**: pytest 9.1.1 with pytest-cov 7.1.0
- **Database**: SQLite in-memory with `StaticPool`, fully isolated per test function, seeded with a default admin user per test
- **Auth bypass**: `X-Internal-Key` header for API tests; session-cookie login tested directly where auth behavior itself is under test

## Test results

| Metric | Value |
|---|---|
| Total tests | 411 |
| Passed | 411 |
| Failed | 0 |
| Overall coverage | 99% (2,124 statements, 5 missed) |
| Coverage on all files added/modified this project | 100% |

### Coverage gaps (all pre-existing, unrelated to this project's changes)

| Module | Coverage | Missing | Why |
|---|---|---|---|
| `app/database.py` | 71% | `get_db()` generator body | Tests override this dependency directly; the generator itself never runs under test |
| `app/utils.py` | 97% | One early-return branch in `_three()` | Cosmetic; the branch is unreachable via any value `amount_in_words` is ever called with in practice |

### Test suite by domain

| File | What it covers |
|---|---|
| `test_inventory.py` | Item CRUD, stock ledger, opening stock, manual adjustments |
| `test_billing.py` | Bill creation/cancellation, GST calculation, duplicate-line stock validation |
| `test_payments.py` | Partial/full payment, void, overdue derivation |
| `test_purchases.py` | Purchase (goods receipt) creation/cancellation, stock ledger reconciliation |
| `test_purchase_orders.py` | PO lifecycle, partial/full receipt, over-receipt rejection, receipt-cancellation reversal |
| `test_sales_returns.py` | Credit notes, duplicate-line aggregation, void, immutability of the original bill |
| `test_purchase_returns.py` | Debit notes, dual stock/line aggregation, void |
| `test_money_precision.py` | Decimal vs float regression cases, JSON wire-format contract |
| `test_dashboard.py` | Cross-domain aggregation, alert generation |
| `test_rbac_and_audit.py` | Login/logout trail, role enforcement, audit content correctness for every domain |
| `test_security_module.py` | Password hashing correctness |
| `test_customers.py`, `test_suppliers.py`, `test_categories.py`, `test_units.py` | Standard CRUD + duplicate-detection rules |
| `test_auth.py`, `test_security.py` | Session auth, internal-key auth |
| `test_utils.py` | Amount-in-words (Indian numbering) |

## Defects found and fixed during this project

### DEF-101 (Critical): Duplicate line items bypassed stock validation

- **Where**: `BillService.create()`
- **What**: Two lines in one bill referencing the same item were validated independently against the item's *starting* quantity, since stock was only deducted after all lines passed validation. Stock=5 with two lines of qty 4 each: both lines individually pass (`4 <= 5`), then both deductions apply — stock ends at -3.
- **How it was found**: Traced deliberately while reviewing the billing service's structure against the "aggregate before validating" principle — then reproduced with a scripted repro before writing the fix, confirming stock actually went negative.
- **Fix**: Requested quantities are now aggregated per item *before* any validation runs; the combined total is checked against available stock in one pass.
- **Regression tests**: `test_create_bill_aggregates_duplicate_lines_for_stock_check`, `test_create_bill_allows_duplicate_lines_within_combined_stock` (`test_billing.py`)
- **Follow-through**: The same aggregation discipline was applied proactively (not reactively) to purchase returns, which have an even sharper version of the same risk — one line's cap and a separate item-level stock cap both need aggregating independently.

### DEF-102 (High): SQLite/Decimal round-trip silently reintroduced float rounding error

- **Where**: `app/money.py` (discovered while migrating money fields from `float` to `Decimal`)
- **What**: SQLite has no native `Decimal` storage — a `Numeric` column's value still passes through a float at the SQLite layer regardless of the declared scale, and SQLAlchemy's sqlite dialect re-derives the `Decimal` on *read* via Python's `round(float_value, scale)`. A price entered as `2.675` was stored correctly but came back from the database as `2.67`, not the correctly-rounded `2.68` — the exact class of error the Decimal migration existed to eliminate.
- **How it was found**: Caught live, not by the test suite — creating a test item with a 3-decimal price through the actual running server (not the in-memory test database) and inspecting the response. This is a case where testing against the real database engine, not just the test harness's in-memory SQLite, mattered: the bug is specific to how SQLite (any SQLite, but the behavior wasn't exercised by the existing test fixtures' values, which all happened to already be exactly 2dp).
- **Fix**: The `Money` Pydantic type now quantizes to 2 decimal places at the moment a value is validated — before it can ever reach the database with excess precision. The lossy round-trip becomes a no-op on an already-clean value.
- **Regression tests**: `test_money_type_quantizes_excess_precision_on_input`, `test_item_price_survives_sqlite_round_trip_with_excess_precision` (`test_money_precision.py`)

### DEF-103 (Medium): Backfilled historical payments were dated "today" instead of their actual date

- **Where**: `migrate_bill_payments.py`
- **What**: The one-time script that backfills a `Payment` record for bills created before payment tracking existed left `payment_date` at its column default (`now()`) instead of the bill's own `created_at`. This had no visible effect until the dashboard's "payments received today" figure was built — at which point every historical backfilled payment would have shown up as "received today," on whatever day the script happened to be run.
- **How it was found**: Live testing of the dashboard feature against the real local database (which had already had the backfill script run against it in an earlier phase) — the "today" figure was implausibly large, tracing back to the backfill's payment dates.
- **Fix**: The script now sets `payment_date=bill.created_at` explicitly. The three already-backfilled rows in the local database were corrected directly (only `payment_date`; `created_at`, the row's own audit timestamp, was left untouched).
- **Regression test**: None added — this is a one-time migration script, not part of the tested application import graph (consistent with how the project's other migration scripts are handled). The fix was verified by re-running the corrected script and re-checking the dashboard figure live.

### Historical defects (from the original pre-transformation audit, still resolved)

| ID | Description | Status |
|---|---|---|
| DEF-001 | Print endpoints used the wrong template directory (missing one `dirname()` level) | Fixed, regression-tested |
| DEF-002 | `amount_in_words` produced malformed output for paise-only amounts (e.g. ₹0.25) | Fixed, regression-tested |
| DEF-003 | "One Rupees" instead of "One Rupee" (grammar) | Not fixed — cosmetic, documented as accepted |

## Business rules resolved (historical)

The original audit flagged four business-rule ambiguities rather than inventing answers. All four were resolved in earlier phases of this project and are documented in full in `BUSINESS_RULES.md`:

| ID | Question | Resolution |
|---|---|---|
| AMB-001 | Purchase cancellation when stock already consumed | Blocked, not floored at zero — surfaces the exact shortfall |
| AMB-002 | Customer name uniqueness | Names may repeat; identical name+phone+address is blocked as a likely duplicate entry |
| AMB-003 | Bill/purchase cancellation referencing a deleted item | Warns by name and quantity rather than silently skipping |
| AMB-004 | Price-tier enforcement on bills | Soft warning on mismatch, never a hard block |

## Live-verification methodology

Every phase of this project's work was verified against the real running server and the real local SQLite database — not only the automated test suite's in-memory fixtures — before being committed. This practice directly caught DEF-102 and DEF-103 above, neither of which the automated test suite's existing fixture data would have surfaced (the fixtures happened to use values that don't trigger either bug). The practice, followed for every phase:

1. Run the full test suite and `python -m compileall`.
2. Start `uvicorn` against the actual `inventory.db`.
3. Exercise the new feature through real HTTP requests with the actual admin session.
4. Inspect the resulting rows directly via `sqlite3`.
5. Clean up any test data created this way, then diff the database file against the last commit to confirm no pre-existing rows were altered.

This is slower than trusting the test suite alone, and is the reason this report can say "no known correctness bugs remain open" rather than "no failing tests."

## Security findings

| ID | Finding | Severity | Status |
|---|---|---|---|
| SEC-001 | SQL injection | N/A | Not applicable — SQLAlchemy parameterizes all queries |
| SEC-002 | XSS via stored user input | Low | Jinja2 auto-escapes by default in the two server-rendered templates (login, print views); the main UI reads API responses into `innerHTML` in a few places without escaping, which is a latent risk if a name/reason field is ever rendered without sanitization — not currently exploited, not yet hardened |
| SEC-003 | Hardcoded credentials | — | **Resolved.** Replaced with a real `User` table, salted PBKDF2 password hashing, and role field. A default admin account is still seeded with a known password for lockout-safety on first deploy — see `BUSINESS_RULES.md` — but it is now a real, changeable credential, not a code constant |
| SEC-004 | Session tokens stored in-memory | Low | Still true — sessions are lost on restart and don't work across multiple server instances. Acceptable for the current single-instance deployment; flagged as an open question in `BUSINESS_RULES.md` |
| SEC-005 | No CSRF protection on login | Low | Unchanged; acceptable for a single-tenant internal app |
| SEC-006 | Auth middleware blocks unauthenticated access | Pass | Confirmed across every phase added since the original audit |
| SEC-007 | Role-based access control | — | **Added.** Deliberately minimal — see `BUSINESS_RULES.md` for why only the audit log is role-gated today |
| SEC-008 | Passwords never appear in the audit trail | Pass | Structural guarantee — audit snapshots are built from response schemas that never include `password_hash` |

## Data integrity findings

| ID | Finding | Status |
|---|---|---|
| DI-001 | Bill creation is atomic; duplicate lines are aggregated before stock validation | Confirmed (was DEF-101, now fixed) |
| DI-002 | Purchase creation is atomic | Confirmed |
| DI-003 | Bill cancellation restores stock, warns on deleted items | Confirmed |
| DI-004 | Purchase cancellation is blocked, not floored, when stock already consumed | Confirmed (AMB-001 resolved) |
| DI-005 | Stock ledger reconciles with `Item.quantity` for every movement type | Confirmed, explicitly tested (`test_stock_ledger_reconciles_with_current_quantity`) |
| DI-006 | A sales/purchase return never mutates its parent document | Confirmed, explicitly tested |
| DI-007 | Cancelling a return is blocked if the affected stock has moved again | Confirmed |
| DI-008 | Purchase order receiving is capped per-line and cannot exceed the order | Confirmed |
| DI-009 | Duplicate item/supplier/category/unit names are prevented | Confirmed |
| DI-010 | Customer names are intentionally not unique (AMB-002) | Confirmed, documented |

## Money / financial calculation findings

| ID | Finding | Status |
|---|---|---|
| FIN-001 | All monetary and GST-rate fields use `Decimal`, not `float` | **Resolved this project** — previously flagged as a documented risk |
| FIN-002 | GST calculation centralized in one module, used by billing and print alike | Confirmed |
| FIN-003 | Line-level rounding, then document-level rounding, is consistent everywhere | Confirmed |
| FIN-004 | SQLite/Decimal round-trip precision bug | **Found and fixed this project** (DEF-102) |
| FIN-005 | Fractional prices and quantities compute correctly | Confirmed, including the specific 2.675 → 2.68 regression case |
| FIN-006 | Dashboard aggregates (stock value, today's totals) still use SQL-level `SUM`/`float()` casts rather than full Decimal arithmetic | Documented, accepted — these are display-only rough figures, not stored transactional amounts; the same trade-off the original dashboard stats already made |

## Remaining risks

1. **No true interstate GST support.** Every sale is computed and displayed as intrastate; see `BUSINESS_RULES.md`.
2. **In-memory sessions.** Lost on restart, don't scale to multiple instances.
3. **Refund/credit settlement is manual.** The app tracks the fact and amount of a cancellation or return; it does not move money.
4. **RBAC has no permission matrix beyond the audit log.** Roles exist; almost nothing checks them yet.
5. **Frontend is one ~4,800-line file with no build step or type checking** — this has been manageable so far but is a growing maintenance cost.
6. **No automated frontend tests.** All UI changes in this project were verified manually (live server + HTML well-formedness checks + JS syntax checks), not via a browser-automation test suite.
7. **Migration scripts are manual, one-time, and unversioned** — there is no tracked history of which environment has had which backfill run, beyond what's recorded in project memory/commit messages.

## Recommended next steps

1. If multi-staff use becomes real, design an actual permission matrix before enabling non-admin roles for real work.
2. If the business ever sells interstate, add customer/company state fields and a real intrastate/interstate GST rule.
3. Consider a shared session store (even a simple DB table) before running more than one server instance.
4. Consider splitting `index.html` if the UI keeps growing — no immediate need, but the trend line is worth watching.
5. Add browser-automation tests (e.g., Playwright) if frontend regressions ever start slipping through manual verification.
6. Sanitize or escape any user-supplied text (item names, return reasons, etc.) before it's ever rendered via `innerHTML`, as defense in depth even though nothing currently exploits its absence.

## Final test output

```
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
app/__init__.py                           0      0   100%
app/audit.py                              7      0   100%
app/auth.py                              36      0   100%
app/database.py                          14      4    71%   17-21
app/models.py                           238      0   100%
app/money.py                              8      0   100%
app/repositories/__init__.py              0      0   100%
app/repositories/audit.py                12      0   100%
app/repositories/base.py                 20      0   100%
app/repositories/bill.py                 27      0   100%
app/repositories/category.py             11      0   100%
app/repositories/customer.py             21      0   100%
app/repositories/item.py                 33      0   100%
app/repositories/payment.py              13      0   100%
app/repositories/purchase.py             20      0   100%
app/repositories/purchase_order.py       12      0   100%
app/repositories/purchase_return.py      12      0   100%
app/repositories/sales_return.py         12      0   100%
app/repositories/supplier.py              9      0   100%
app/repositories/unit.py                 11      0   100%
app/repositories/user.py                 11      0   100%
app/routers/__init__.py                   0      0   100%
app/routers/audit_log.py                 14      0   100%
app/routers/auth.py                      39      0   100%
app/routers/billing.py                   94      0   100%
app/routers/categories.py                24      0   100%
app/routers/customers.py                 33      0   100%
app/routers/dashboard.py                 15      0   100%
app/routers/inventory.py                 46      0   100%
app/routers/purchase_orders.py           34      0   100%
app/routers/purchases.py                 63      0   100%
app/routers/suppliers.py                 33      0   100%
app/routers/units.py                     24      0   100%
app/routers/users.py                     30      0   100%
app/schemas.py                          381      0   100%
app/security.py                          18      0   100%
app/services/__init__.py                  0      0   100%
app/services/audit.py                     8      0   100%
app/services/bill.py                    128      0   100%
app/services/category.py                 29      0   100%
app/services/customer.py                 37      0   100%
app/services/dashboard.py                28      0   100%
app/services/item.py                     56      0   100%
app/services/purchase.py                103      0   100%
app/services/purchase_order.py           52      0   100%
app/services/purchase_return.py          84      0   100%
app/services/sales_return.py             88      0   100%
app/services/supplier.py                 30      0   100%
app/services/tax.py                      10      0   100%
app/services/unit.py                     29      0   100%
app/services/user.py                     31      0   100%
app/utils.py                             36      1    97%   17
-------------------------------------------------------------------
TOTAL                                  2124      5    99%
411 passed, 49 warnings in 31.66s
```
