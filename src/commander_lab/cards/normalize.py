from __future__ import annotations

import re
import unicodedata

_APOSTROPHES = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        "／": "/",
    }
)

_SET_SUFFIX = re.compile(
    r"\s+(?:\([A-Za-z0-9]{2,8}\)|\[[A-Za-z0-9]{2,8}\])(?:\s+[#A-Za-z0-9-]+)?\s*$"
)
_COLLECTOR_SUFFIX = re.compile(r"\s+#?\d+[A-Za-z]?\s*$")
_QUANTITY_PREFIX = re.compile(r"^\s*(\d+)\s*[xX×]?\s+(.+?)\s*$")


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(_APOSTROPHES)


def strip_export_annotations(value: str) -> str:
    value = normalize_unicode(value).strip()
    value = re.sub(r"\s+\*F\*\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+foil\s*$", "", value, flags=re.IGNORECASE)
    value = _SET_SUFFIX.sub("", value)
    return value.strip()


def normalize_oracle_name(value: str) -> str:
    value = strip_export_annotations(value)
    value = re.sub(r"\s*/\s*/\s*", " // ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def oracle_lookup_key(value: str) -> str:
    normalized = normalize_oracle_name(value).casefold()
    normalized = normalized.replace("æ", "ae")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def split_quantity_and_name(line: str) -> tuple[int, str]:
    match = _QUANTITY_PREFIX.match(normalize_unicode(line))
    if not match:
        return 1, normalize_oracle_name(line)
    quantity = int(match.group(1))
    return quantity, normalize_oracle_name(match.group(2))
