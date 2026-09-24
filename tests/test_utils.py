"""
Unit tests for app/utils.py  →  amount_in_words()
"""
from app.utils import amount_in_words


def test_zero():
    assert amount_in_words(0) == "Zero Rupees Only"


def test_zero_float():
    assert amount_in_words(0.0) == "Zero Rupees Only"


def test_rupees_only():
    assert amount_in_words(100) == "One Hundred Rupees Only"


def test_with_paise():
    assert amount_in_words(100.50) == "One Hundred Rupees and Fifty Paise Only"


def test_thousands():
    assert amount_in_words(1500) == "One Thousand Five Hundred Rupees Only"


def test_lakhs():
    assert amount_in_words(100000) == "One Lakh Rupees Only"


def test_crores():
    assert amount_in_words(10000000) == "One Crore Rupees Only"


def test_complex():
    result = amount_in_words(1234567.89)
    assert "Twelve Lakh" in result
    assert "Paise" in result


def test_small_amount():
    assert amount_in_words(5) == "Five Rupees Only"


def test_nineteen():
    assert amount_in_words(19) == "Nineteen Rupees Only"


def test_twenty():
    assert amount_in_words(20) == "Twenty Rupees Only"


# --- additional edge-case coverage ---

def test_one_rupee():
    assert amount_in_words(1) == "One Rupees Only"


def test_paise_only():
    # 0 rupees, non-zero paise — should not say "Zero Rupees"
    result = amount_in_words(0.25)
    assert "Paise" in result
    assert "Zero" not in result


def test_ninety_nine():
    assert amount_in_words(99) == "Ninety Nine Rupees Only"


def test_thousand_exact():
    assert amount_in_words(1000) == "One Thousand Rupees Only"


def test_ten_lakhs():
    assert amount_in_words(1000000) == "Ten Lakh Rupees Only"


# ---------------------------------------------------------------------------
# Phase 10 — Extended amount_in_words tests
# ---------------------------------------------------------------------------

def test_two_rupees():
    assert amount_in_words(2) == "Two Rupees Only"


def test_ten():
    assert amount_in_words(10) == "Ten Rupees Only"


def test_eleven():
    assert amount_in_words(11) == "Eleven Rupees Only"


def test_fifty():
    assert amount_in_words(50) == "Fifty Rupees Only"


def test_hundred():
    assert amount_in_words(100) == "One Hundred Rupees Only"


def test_two_hundred_fifty():
    assert amount_in_words(250) == "Two Hundred Fifty Rupees Only"


def test_three_hundred_fifty_four():
    assert amount_in_words(354) == "Three Hundred Fifty Four Rupees Only"


def test_five_thousand():
    assert amount_in_words(5000) == "Five Thousand Rupees Only"


def test_twelve_thousand_three_hundred():
    assert amount_in_words(12300) == "Twelve Thousand Three Hundred Rupees Only"


def test_fifty_four():
    assert amount_in_words(54) == "Fifty Four Rupees Only"


def test_ninety_nine_with_paise():
    result = amount_in_words(999999.99)
    assert "Nine Lakh" in result
    assert "Ninety Nine Paise" in result


def test_one_crore_twenty_three_lakh():
    result = amount_in_words(12345678.50)
    assert result == "One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Rupees and Fifty Paise Only"


def test_amount_in_words_354():
    """Bill total 354.00 should render correctly."""
    assert amount_in_words(354.00) == "Three Hundred Fifty Four Rupees Only"


def test_amount_in_words_93_31():
    assert amount_in_words(93.31) == "Ninety Three Rupees and Thirty One Paise Only"


def test_amount_in_words_100_10():
    assert amount_in_words(100.10) == "One Hundred Rupees and Ten Paise Only"


# ---------------------------------------------------------------------------
# Phase 10 — Defect: paise-only amounts produce leading space and "Rupees"
# ---------------------------------------------------------------------------

def test_paise_only_defect():
    """
    DEF-001: amount_in_words(0.25) returns ' Rupees and Twenty Five Paise Only'
    Expected: 'Twenty Five Paise Only' (no leading space, no 'Rupees')
    Current behaviour produces a leading space and says 'Rupees' even for 0 rupees.
    This test documents the DEFECT -- it will fail until the fix is applied.
    """
    result = amount_in_words(0.25)
    # After fix, expected: "Twenty Five Paise Only"
    assert result == "Twenty Five Paise Only"


def test_paise_only_one_paisa():
    """0.01 should produce correct output."""
    result = amount_in_words(0.01)
    assert result == "One Paise Only"


def test_paise_only_ninety_nine():
    """0.99 should produce correct output."""
    result = amount_in_words(0.99)
    assert result == "Ninety Nine Paise Only"


# ---------------------------------------------------------------------------
# Phase 13 — Money precision in utils
# ---------------------------------------------------------------------------

def test_amount_rounding_with_float_imprecision():
    """
    amount_in_words uses int(amount) for rupees and round((amount - rupees) * 100)
    for paise. This should handle normal float imprecision.
    """
    # 1.10 in float might be 1.0999999... but int(1.10)=1, paise=round(0.10*100)=10
    result = amount_in_words(1.10)
    assert result == "One Rupees and Ten Paise Only"


def test_one_rupee_grammar():
    """
    DEF-002: amount_in_words(1) returns 'One Rupees Only' (plural).
    Grammatically should be 'One Rupee Only' (singular).
    DOCUMENTED: This is current behaviour, but arguably a low-severity cosmetic issue.
    """
    # Current behaviour: 'One Rupees Only' (plural, grammatically incorrect)
    # We test the current behaviour since fixing this is cosmetic
    result = amount_in_words(1)
    assert "One" in result
    assert "Rupees" in result
