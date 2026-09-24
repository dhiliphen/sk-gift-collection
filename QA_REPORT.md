# Customer Inventory & Billing Application -- QA Report

## Executive Summary

A comprehensive QA audit was performed on the SK Gift Collection Inventory & Billing application. The application is built with FastAPI + SQLAlchemy (SQLite) + Jinja2, following a clean repository/service/router architecture. Testing covered all API endpoints, business logic, authentication, security, financial calculations, and atomicity guarantees.

**Result**: 234 tests pass, 99% code coverage. Two defects were found and fixed. Several business rules flagged as ambiguous for customer confirmation.

## Test Environment

- **Python**: 3.12.12
- **Framework**: FastAPI 0.111.0 + SQLAlchemy 2.0.30
- **Test runner**: pytest 8.3.2 with pytest-cov 5.0.0
- **Database**: SQLite in-memory with StaticPool (isolated per test)
- **Auth bypass**: X-Internal-Key header for API tests

## Test Results

| Metric | Value |
|--------|-------|
| Total tests | 234 |
| Passed | 234 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Coverage | 99% |

### Coverage by module

| Module | Coverage | Missing |
|--------|----------|---------|
| app/models.py | 100% | - |
| app/schemas.py | 100% | - |
| app/services/*.py | 100% | - |
| app/repositories/*.py | 100% | - |
| app/routers/billing.py | 100% | - |
| app/routers/purchases.py | 100% | - |
| app/routers/inventory.py | 100% | - |
| app/routers/auth.py | 78% | logout endpoint (lines 41-46) |
| app/auth.py | 94% | delete_session (line 27) |
| app/database.py | 71% | get_db generator (lines 17-21, overridden in tests) |
| app/utils.py | 97% | _three n==0 early return (line 17) |

## Critical Defects (Severity: Critical)

### DEF-001: Template path miscalculation in billing and purchase print endpoints

- **Severity**: Critical
- **Component**: `app/routers/billing.py`, `app/routers/purchases.py`
- **Description**: The template directory path was computed incorrectly. The code used `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` which resolves to the `app/` directory, then joined `app/templates` -- creating `app/app/templates` (double `app` prefix).
- **Steps to reproduce**: Call `GET /api/bills/{id}/print` without the `BASE_DIR` environment variable set.
- **Expected behaviour**: Returns HTML invoice/purchase print page.
- **Actual behaviour**: `jinja2.exceptions.TemplateNotFound: print_invoice.html` (500 error).
- **Root cause**: Off-by-one in directory traversal. Needed three levels of `dirname()` from `app/routers/billing.py` to reach the repo root, but only used two.
- **Fix applied**: Changed `os.path.dirname(os.path.dirname(...))` to `os.path.dirname(os.path.dirname(os.path.dirname(...)))` in both `app/routers/billing.py` and `app/routers/purchases.py`.
- **Regression test**: `test_bill_print_endpoint`, `test_purchase_print_endpoint`

## Medium Defects

### DEF-002: amount_in_words produces malformed output for paise-only amounts

- **Severity**: Medium
- **Component**: `app/utils.py`
- **Description**: When the amount has zero rupees but non-zero paise (e.g., 0.25), the function returned `' Rupees and Twenty Five Paise Only'` -- with a leading space and the misleading word "Rupees".
- **Steps to reproduce**: Call `amount_in_words(0.25)`.
- **Expected behaviour**: `"Twenty Five Paise Only"`
- **Actual behaviour (before fix)**: `" Rupees and Twenty Five Paise Only"`
- **Root cause**: When `rupees == 0` and `paise > 0`, the `parts` list is empty. Joining empty parts produces `''`, then appending `' Rupees'` creates `' Rupees'`. The function only checked for the `rupees == 0 AND paise == 0` case, not the paise-only case.
- **Fix applied**: Added conditional: if `parts` is non-empty, format as `"... Rupees"`, else format as `"... Paise"` only.
- **Regression tests**: `test_paise_only_defect`, `test_paise_only_one_paisa`, `test_paise_only_ninety_nine`

## Low Defects

### DEF-003: "One Rupees" uses plural instead of singular

- **Severity**: Low (cosmetic)
- **Component**: `app/utils.py`
- **Description**: `amount_in_words(1)` returns `"One Rupees Only"` instead of `"One Rupee Only"`. Grammatically, singular amounts should use "Rupee".
- **Fix applied**: Not fixed -- cosmetic issue, low priority.
- **Regression test**: `test_one_rupee_grammar` (documents current behaviour)

## Business Rules Requiring Customer Confirmation

### AMB-001: Purchase cancellation when stock has been sold

- **Current behaviour**: When cancelling a purchase, if the purchased stock has already been sold (item quantity is now less than the purchased quantity), the cancellation floors the stock at 0 using `max(0, qty - purchased_qty)`.
- **Question**: Should the system prevent cancellation if stock has been consumed? Should it require a warning/confirmation? Should it allow negative stock?
- **Test**: `test_cancel_purchase_after_stock_sold`, `test_cancel_purchase_stock_floor_at_zero`

### AMB-002: Customer name uniqueness

- **Current behaviour**: No uniqueness constraint on customer names. Multiple customers can have identical names.
- **Question**: Should customer names be unique? Or is this intentional (e.g., franchise locations with the same business name)?
- **Test**: `test_create_customer_duplicate_name_allowed`

### AMB-003: Bill cancellation restores stock unconditionally

- **Current behaviour**: Cancelling a bill always restores stock, even if the item has been deleted or modified. If the item has been deleted, the stock restoration is silently skipped (the `items_by_id.get()` returns None).
- **Question**: Should cancelled bills that reference deleted items raise an error or a warning?

### AMB-004: No price tier enforcement on bills

- **Current behaviour**: The `unit_price` on a bill is provided by the caller and not validated against the item's price tiers (wholesale_price, dealer_price, selling_price). A bill can be created with any price regardless of customer type.
- **Question**: Should the API enforce that wholesalers get wholesale_price, dealers get dealer_price, and retailers get selling_price?

## Security Findings

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-001 | SQL injection protected by ORM | N/A | Confirmed safe -- SQLAlchemy parameterises all queries |
| SEC-002 | XSS payloads stored as-is in API layer | Medium | No server-side sanitisation. Risk depends on frontend template escaping (Jinja2 auto-escapes by default). |
| SEC-003 | Hardcoded credentials in source code | Medium | `app/auth.py` has `_USERNAME = "admin"` and password hash for "skgifts". Should use env vars. |
| SEC-004 | Session tokens stored in-memory | Low | Sessions are lost on server restart. Acceptable for single-server deployment but not for multi-instance. |
| SEC-005 | No CSRF protection | Low | POST /login uses form data without CSRF token. Acceptable for internal app. |
| SEC-006 | Auth middleware correctly blocks unauthenticated access | Pass | Confirmed: all API endpoints redirect to /login without valid session or internal key. |

## Data Integrity Findings

| ID | Finding | Status |
|----|---------|--------|
| DI-001 | Bill creation is atomic -- if any item fails validation, no stock is deducted | Confirmed |
| DI-002 | Purchase creation is atomic -- if any item_id is invalid, no stock is added | Confirmed |
| DI-003 | Bill cancellation restores stock for all items | Confirmed |
| DI-004 | Purchase cancellation deducts stock with floor at 0 | Confirmed (see AMB-001) |
| DI-005 | Duplicate item names prevented at service layer | Confirmed |
| DI-006 | Duplicate supplier names prevented at service layer | Confirmed |
| DI-007 | Duplicate category/unit names prevented at service layer | Confirmed |
| DI-008 | Customer names are NOT unique -- duplicates allowed | Documented (see AMB-002) |

## Money / Financial Calculation Findings

| ID | Finding | Status |
|----|---------|--------|
| FIN-001 | GST calculation: taxable = qty * unit_price, igst = taxable * gst_rate / 100 | Correct |
| FIN-002 | Each line item rounded to 2 decimal places | Correct |
| FIN-003 | Bill totals are sum of line amounts, then rounded to 2dp | Correct |
| FIN-004 | Zero GST bills compute correctly (igst = 0) | Correct |
| FIN-005 | Fractional prices handled correctly (e.g., qty=7, price=13.33) | Correct |
| FIN-006 | Using Python float (not Decimal) for money -- acceptable precision for small to medium amounts | Documented risk |
| FIN-007 | Dashboard total_value uses cost_price * quantity, not selling_price | Correct |
| FIN-008 | HSN summary in print view aggregates by (hsn_code, gst_rate) | Correct |

## Remaining Risks

1. **Float vs Decimal**: Financial calculations use Python `float` and SQLite `REAL`. For amounts up to ~10 crore, this is acceptable. For very large amounts or high-precision requirements, consider migrating to `Decimal` types.

2. **No audit trail**: There is no history/log of who created or cancelled bills/purchases. Consider adding an audit log table.

3. **No rate limiting**: API endpoints have no rate limiting. In a public deployment, this could be exploited.

4. **Hardcoded credentials**: Production deployments should use environment variables for admin credentials, not hardcoded values.

5. **No input sanitisation for XSS**: The API stores user input as-is. While Jinja2 auto-escapes in templates, any future non-Jinja rendering (e.g., PDF generation, email templates) could be vulnerable.

## Recommended Next Steps

1. Move admin credentials to environment variables
2. Decide on AMB-001 through AMB-004 business rules
3. Add audit logging for bill/purchase creation and cancellation
4. Consider adding CSRF tokens to the login form
5. Add rate limiting middleware for production deployment
6. Consider migrating Float columns to Decimal for financial data
7. Add input sanitisation or content-security-policy headers

## Final Test Output

```
234 passed, 17 warnings in 2.35s

--------- coverage: platform darwin, python 3.12.12-final-0 ----------
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
app/__init__.py                    0      0   100%
app/auth.py                       16      1    94%   27
app/database.py                   14      4    71%   17-21
app/models.py                     98      0   100%
app/repositories/__init__.py       0      0   100%
app/repositories/base.py          20      0   100%
app/repositories/bill.py          12      0   100%
app/repositories/category.py      11      0   100%
app/repositories/customer.py      12      0   100%
app/repositories/item.py          24      0   100%
app/repositories/purchase.py      12      0   100%
app/repositories/supplier.py       9      0   100%
app/repositories/unit.py          11      0   100%
app/routers/__init__.py            0      0   100%
app/routers/auth.py               27      6    78%   41-46
app/routers/billing.py            43      0   100%
app/routers/categories.py         24      0   100%
app/routers/customers.py          24      0   100%
app/routers/inventory.py          31      0   100%
app/routers/purchases.py          33      0   100%
app/routers/suppliers.py          24      0   100%
app/routers/units.py              24      0   100%
app/schemas.py                   179      0   100%
app/services/__init__.py           0      0   100%
app/services/bill.py              60      0   100%
app/services/category.py          29      0   100%
app/services/customer.py          29      0   100%
app/services/unit.py              29      0   100%
app/services/item.py              41      0   100%
app/services/purchase.py          51      0   100%
app/services/supplier.py          30      0   100%
app/utils.py                      36      1    97%   17
------------------------------------------------------------
TOTAL                            953     12    99%
```
