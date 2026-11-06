"""Read-only request policy.

Every HTTP request the client sends (including each redirect hop) passes
through :meth:`ReadOnlyPolicy.check`. Anything that is not clearly a read is
refused *before* it leaves the machine.

The rules, in order:

1. Only ``https`` on the configured ILIAS host.
2. Only ``GET``. The single exception is the login form ``POST``, and only
   while :meth:`ReadOnlyPolicy.login_window` is open for that exact URL.
3. Only known entry points (``ilias.php``, ``login.php``, static ``/data/``
   files) and permanent links in their plain ``type/id`` form. ``goto``
   targets can carry suffixes, e.g. registration codes that join a course.
4. No ``rtoken`` parameter. ILIAS attaches this CSRF token to links whose GET
   changes state (remove from favourites, mark as read, leave, delete...).
5. No forum thread or posting parameters: opening a thread marks it as read.
6. No mail GUI: opening a mail marks it as read.
7. ``cmd`` / ``fallbackCmd`` must be on an allowlist of viewing commands.
   Some state-changing GETs carry no ``rtoken`` (the calendar block's
   ``setPdModeEvents``, for one), so unknown commands are refused with a
   message that names them; a new safe command is added deliberately.
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import parse_qsl, urlsplit


class PolicyViolation(RuntimeError):
    """A request was refused because it is not clearly read-only."""


# Commands that only display or deliver content. Compared lower-case.
SAFE_CMDS: frozenset[str] = frozenset(
    {
        "",
        "view",
        "show",
        "render",
        "frameset",
        "infoscreen",
        "showsummary",
        "showoverview",
        "jumptoselecteditems",
        "jumptomemberships",
        "sendfile",
        "download",
        "downloadfile",
        "showthreads",
        "shownews",
        "showcontent",
        "force_login",
        "showloginpage",
    }
)

# Query keys that are never sent (lower-case).
FORBIDDEN_KEYS: dict[str, str] = {
    "rtoken": "link carries an rtoken (ILIAS uses it for state-changing links)",
    "thr_pk": "opening a forum thread marks its posts as read",
    "pos_pk": "opening a forum posting marks it as read",
}

FORBIDDEN_BASECLASSES: dict[str, str] = {
    "ilmailgui": "opening mail marks it as read",
}

# Permanent links. Only the plain "type + id" forms (and file downloads):
# goto targets can carry suffixes such as registration codes that join a course.
GOTO_PATHS = (
    re.compile(r"^/goto\.php/[a-z]{2,6}/\d+(?:/download)?/?$"),
    re.compile(r"^/go/[a-z]{2,6}/\d+/?$"),
    re.compile(r"^/goto_[A-Za-z0-9_]+?_[a-z]{2,6}_\d+(?:_download)?\.html$"),
)
GOTO_TARGET = re.compile(r"^[a-z]{2,6}_\d+(?:_download)?$")
ALLOWED_PATHS: frozenset[str] = frozenset(
    {"/", "/index.php", "/ilias.php", "/login.php", "/error.php", "/goto.php"}
)
STATIC_PREFIX = "/data/"


class ReadOnlyPolicy:
    def __init__(self, host: str) -> None:
        self.host = host.lower()
        self._lock = threading.Lock()
        self._login_post_url: str | None = None

    @contextmanager
    def login_window(self, post_url: str) -> Iterator[None]:
        """Allow exactly one POST target (the login form) for the duration."""
        with self._lock:
            self._login_post_url = post_url
        try:
            yield
        finally:
            with self._lock:
                self._login_post_url = None

    def check(self, method: str, url: str) -> None:
        method = method.upper()
        parts = urlsplit(url)

        if parts.scheme != "https":
            raise PolicyViolation(f"refused non-https URL: {parts.scheme}://{parts.netloc}")
        if (parts.hostname or "").lower() != self.host:
            raise PolicyViolation(f"refused request to another host: {parts.hostname}")

        if method != "GET":
            with self._lock:
                allowed = self._login_post_url
            if method == "POST" and allowed is not None and _same_url(url, allowed):
                return  # the login form, nothing else
            raise PolicyViolation(f"refused {method} request (read-only client)")

        path = parts.path or "/"
        if "rcode" in url.lower():
            raise PolicyViolation("refused: registration-code links join a course")
        if not (
            path in ALLOWED_PATHS
            or path.startswith(STATIC_PREFIX)
            or any(p.match(path) for p in GOTO_PATHS)
        ):
            raise PolicyViolation(f"refused unknown ILIAS path: {path}")

        params = parse_qsl(parts.query, keep_blank_values=True)
        if path == "/goto.php":
            target = dict((k.lower(), v) for k, v in params).get("target", "")
            if target and not GOTO_TARGET.match(target):
                raise PolicyViolation(f"refused goto target {target!r}: only plain type_id links")
        for key, _ in params:  # the most specific reasons first
            if key.lower() in FORBIDDEN_KEYS:
                raise PolicyViolation(f"refused: {FORBIDDEN_KEYS[key.lower()]}")
        for key, value in params:
            k = key.lower()
            if k.startswith("cmd["):
                raise PolicyViolation(f"refused form command parameter: {key}")
            if k == "baseclass" and value.lower() in FORBIDDEN_BASECLASSES:
                raise PolicyViolation(f"refused: {FORBIDDEN_BASECLASSES[value.lower()]}")
            if k in ("cmd", "fallbackcmd") and value.lower() not in SAFE_CMDS:
                raise PolicyViolation(
                    f"refused ILIAS command {key}={value!r}: not on the read-only allowlist"
                )

    def describe(self) -> dict:
        return {
            "host": self.host,
            "methods": "GET only (plus the login form POST during login)",
            "allowed_cmds": sorted(c for c in SAFE_CMDS if c),
            "blocked_params": sorted(FORBIDDEN_KEYS),
            "blocked_baseclasses": sorted(FORBIDDEN_BASECLASSES),
        }


def _same_url(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (
        pa.scheme == pb.scheme
        and (pa.hostname or "").lower() == (pb.hostname or "").lower()
        and pa.path == pb.path
        and sorted(parse_qsl(pa.query, keep_blank_values=True))
        == sorted(parse_qsl(pb.query, keep_blank_values=True))
    )
