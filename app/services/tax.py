"""
Centralized GST calculation. Previously this math was duplicated between
BillService.create() and the print-invoice route; both now call here so
there is exactly one place that knows how tax is computed.

Documented business-rule assumption (per the existing behavior this
codebase already had before this module existed — not invented here):
this business treats every sale as intrastate. There is no customer or
company "state" field in the data model to detect an interstate sale, so
a single combined tax amount is calculated and stored (in the historically
named `igst_amount` column), and only split into CGST + SGST halves at
print time for display on the invoice. Supporting true interstate IGST
would require capturing customer/seller state and is a data-model
decision for the business owner, not something to infer here.
"""
from decimal import Decimal


def calculate_line_tax(quantity: int, unit_price: Decimal, gst_rate: Decimal) -> dict:
    """Taxable amount, tax amount, and line total for one bill/purchase line."""
    taxable_amount = round(Decimal(quantity) * unit_price, 2)
    tax_amount = round(taxable_amount * gst_rate / 100, 2)
    line_total = round(taxable_amount + tax_amount, 2)
    return {
        "taxable_amount": taxable_amount,
        "tax_amount": tax_amount,
        "line_total": line_total,
    }


def split_cgst_sgst(taxable_amount: Decimal, gst_rate: Decimal) -> dict:
    """Splits the combined tax on a taxable amount into equal CGST/SGST
    halves for display (see module docstring on the intrastate assumption).
    Halves first, then doubles for total_tax, matching this app's original
    print-invoice arithmetic so previously printed figures don't shift."""
    half = round(taxable_amount * gst_rate / 100 / 2, 2)
    total_tax = round(half * 2, 2)
    return {"cgst": half, "sgst": half, "total_tax": total_tax}
