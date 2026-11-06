"""Parse the date strings ILIAS renders (English and German UI).

Dates are returned as ISO strings in Europe/Berlin: ``2026-11-05T14:00+01:00``
when ILIAS shows a time, ``2026-11-05`` when it shows only a day.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo

    BERLIN = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover - missing tz database
    BERLIN = None  # type: ignore[assignment]

_MONTHS = {
    "jan": 1, "januar": 1, "january": 1, "jän": 1,
    "feb": 2, "februar": 2, "february": 2,
    "mar": 3, "mär": 3, "mrz": 3, "march": 3, "märz": 3,
    "apr": 4, "april": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6, "juni": 6,
    "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "okt": 10, "october": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "dez": 12, "december": 12, "dezember": 12,
}
_RELATIVE = {
    "today": 0, "heute": 0,
    "yesterday": -1, "gestern": -1,
    "tomorrow": 1, "morgen": 1,
}

_TIME = r"(?:,?\s*(?P<h>\d{1,2}):(?P<mi>\d{2}))?"
_PATTERNS = [
    # 5. Nov 2026, 14:00  |  05. November 2026  |  5. Mär. 2026, 9:15
    re.compile(r"\b(?P<d>\d{1,2})\.\s*(?P<mon>[A-Za-zäÄ]{3,9})\.?\s+(?P<y>\d{4})" + _TIME),
    # Nov 5, 2026 14:00  |  November 5, 2026, 2:00
    re.compile(r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),\s*(?P<y>\d{4})" + _TIME),
    # 05.11.2026 14:00  |  5.11.2026, 14:00
    re.compile(r"\b(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})" + _TIME),
    # 2026-11-05 14:00
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?:[ T](?P<h>\d{2}):(?P<mi>\d{2}))?"),
    # Today, 14:00  |  Gestern, 09:30
    re.compile(r"\b(?P<rel>today|yesterday|tomorrow|heute|gestern|morgen)\b" + _TIME, re.I),
]


def now_berlin() -> datetime:
    return datetime.now(BERLIN) if BERLIN else datetime.now()


def find_date(text: str, now: datetime | None = None) -> str | None:
    """First ILIAS-style date in ``text`` as an ISO string, or None."""
    dates = find_all_dates(text, now)
    return dates[0] if dates else None


def find_all_dates(text: str, now: datetime | None = None) -> list[str]:
    """All dates in ``text``, in order of appearance, as ISO strings."""
    found: list[tuple[int, int, str]] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            value = _build(match.groupdict(), now)
            if value is None:
                continue
            start, end = match.span()
            if any(start < e and s < end for s, e, _ in found):
                continue  # overlaps a date found by an earlier pattern
            found.append((start, end, value))
    return [v for _, _, v in sorted(found)]


def parse_iso(value: str) -> datetime:
    """Inverse of the ISO strings above; day-only values become midnight Berlin."""
    if len(value) == 10:
        d = date.fromisoformat(value)
        return datetime(d.year, d.month, d.day, tzinfo=BERLIN)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None and BERLIN is not None:
        parsed = parsed.replace(tzinfo=BERLIN)
    return parsed


def _build(g: dict, now: datetime | None) -> str | None:
    try:
        if g.get("rel"):
            base = (now or now_berlin()).date() + timedelta(days=_RELATIVE[g["rel"].lower()])
            day, month, year = base.day, base.month, base.year
        else:
            day, year = int(g["d"]), int(g["y"])
            if g.get("m"):
                month = int(g["m"])
            else:
                name = g["mon"].lower().rstrip(".")
                month = _MONTHS.get(name) or _MONTHS.get(name[:3])
                if month is None:
                    return None
        if not g.get("h"):
            return date(year, month, day).isoformat()
        value = datetime(year, month, day, int(g["h"]), int(g["mi"]), tzinfo=BERLIN)
        return value.isoformat(timespec="minutes")
    except (ValueError, KeyError, TypeError):
        return None
