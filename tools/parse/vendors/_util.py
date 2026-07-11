# Shared helpers for vendor parsers.

import re

_DANISH_NUMBER_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$")


def parse_danish_number(text):
    """Parse a Danish-formatted number string to a float.

    Danish convention: '.' is the thousands separator, ',' is the decimal
    point. "2.412,30" -> 2412.30, "1,00" -> 1.0, "15" -> 15.0.

    Returns None if `text` doesn't look like a Danish number (so callers can
    treat it as "not a number" rather than crashing on OCR garbage).
    """
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    if not _DANISH_NUMBER_RE.match(t):
        return None
    normalized = t.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def looks_like_danish_number(text):
    return parse_danish_number(text) is not None
