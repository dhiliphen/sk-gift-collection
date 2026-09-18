_ONES = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
    'Seventeen', 'Eighteen', 'Nineteen',
]
_TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + (' ' + _ONES[n % 10] if n % 10 else '')


def _three(n: int) -> str:
    if n == 0:
        return ''
    if n < 100:
        return _two(n)
    return _ONES[n // 100] + ' Hundred' + (' ' + _two(n % 100) if n % 100 else '')


def amount_in_words(amount: float) -> str:
    rupees = int(amount)
    paise  = round((amount - rupees) * 100)

    if rupees == 0 and paise == 0:
        return 'Zero Rupees Only'

    parts = []
    n = rupees

    if n >= 10_000_000:
        parts.append(_three(n // 10_000_000) + ' Crore')
        n %= 10_000_000
    if n >= 100_000:
        parts.append(_three(n // 100_000) + ' Lakh')
        n %= 100_000
    if n >= 1_000:
        parts.append(_three(n // 1_000) + ' Thousand')
        n %= 1_000
    if n > 0:
        parts.append(_three(n))

    result = ' '.join(parts) + ' Rupees'
    if paise:
        result += ' and ' + _two(paise) + ' Paise'
    return result + ' Only'
