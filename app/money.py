"""
Shared Decimal type for monetary and rate fields (prices, tax amounts,
payments, GST rates). Pydantic validates/coerces input (float, int, str)
into an exact Decimal via string conversion — never through the binary
float constructor — so classic float traps (0.1 + 0.2 != 0.3) never enter
the calculation. On the way out, values are serialized back to a plain
JSON number so the API wire format and existing frontend are unchanged.

Every value is quantized to 2 decimal places the moment it enters the
system (matching the paisa as the smallest real-world unit this business
deals in). This isn't just a business-precision choice: SQLite has no
native Decimal storage, so a Numeric column's value is round-tripped
through a float at the SQLite layer regardless of the declared scale,
and SQLAlchemy's sqlite dialect re-derives the Decimal on read via
Python's float round() to that scale — which reintroduces the exact
binary-float rounding error this module exists to avoid (e.g. a raw
2.675 would silently come back as 2.67). Quantizing to 2dp up front
means the round-trip is a no-op: what goes in is already what a correct
2dp rounding would produce, so there is nothing left for the lossy
float round-trip to get wrong.
"""
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Annotated
from pydantic import BeforeValidator, PlainSerializer

_TWO_PLACES = Decimal("0.01")


def _quantize(value) -> Decimal:
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return d.quantize(_TWO_PLACES, rounding=ROUND_HALF_EVEN)


Money = Annotated[
    Decimal,
    BeforeValidator(_quantize),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
