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
