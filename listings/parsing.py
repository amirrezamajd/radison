import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NUMBER = r"(\d[\d,٬.]*)"

_UNITS = (
    ("میلیارد", 1_000_000_000),
    ("میلیون", 1_000_000),
    ("هزار", 1_000),
)


def normalize_digits(text: str) -> str:
    return (text or "").translate(_DIGITS)


def normalize_persian(text: str) -> str:
    return normalize_digits(text).replace("ي", "ی").replace("ك", "ک").strip()


def _to_number(raw: str) -> float | None:
    cleaned = raw.replace(",", "").replace("٬", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_price(text: str) -> int | None:
    """Return the first price in toman, e.g. '21,000,000,000 تومان' or '۳.۵ میلیارد'."""
    clean = normalize_digits(text)
    match = re.search(_NUMBER + r"\s*(میلیارد|میلیون|هزار)?", clean)
    if not match:
        return None
    value = _to_number(match.group(1))
    if value is None:
        return None
    unit = match.group(2)
    for name, factor in _UNITS:
        if unit == name:
            value *= factor
            break
    if "ریال" in clean and "تومان" not in clean:
        value /= 10
    return int(value) if value > 0 else None


def parse_area(specs: list[str]) -> int | None:
    for spec in specs or []:
        match = re.search(_NUMBER + r"\s*متر(?!ی)", normalize_digits(spec))
        if match:
            value = _to_number(match.group(1))
            if value:
                return int(value)
    return None


def parse_bedrooms(specs: list[str]) -> int | None:
    for spec in specs or []:
        match = re.search(r"(\d+)\s*خواب", normalize_digits(spec))
        if match:
            return int(match.group(1))
    return None
