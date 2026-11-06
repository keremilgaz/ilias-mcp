"""HTTP client: guarded transport, rate limiting, lazy login and re-login."""

from __future__ import annotations

import logging
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from . import parsers
from .config import Settings
from .credentials import keychain_password
from .policy import PolicyViolation, ReadOnlyPolicy

log = logging.getLogger("ilias_mcp")

USER_AGENT = "ilias-mcp/0.1 (personal read-only client)"


class IliasError(RuntimeError):
    pass


class LoginError(IliasError):
    pass


class BudgetExceeded(IliasError):
    pass


@dataclass
class Page:
    url: str  # final URL after redirects
    html: str


@dataclass
class FileDownload:
    url: str
    content: bytes
    filename: str | None
    content_type: str


class GuardedTransport(httpx.BaseTransport):
    """Checks every request (redirect hops included) and spaces them out."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        policy: ReadOnlyPolicy,
        min_interval: float,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        on_request: Callable[[httpx.Request], None] | None = None,
    ) -> None:
        self.inner = inner
        self.policy = policy
        self.min_interval = min_interval
        self.sleep = sleep
        self.clock = clock
        self.on_request = on_request
        self._lock = threading.Lock()
        self._last: float | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.policy.check(request.method, str(request.url))
        if self.on_request is not None:
            self.on_request(request)
        with self._lock:
            if self._last is not None:
                wait = self._last + self.min_interval - self.clock()
                if wait > 0:
                    self.sleep(wait)
            self._last = self.clock()
        log.info("%s %s", request.method, _describe(str(request.url)))
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()


def _describe(url: str) -> str:
    """Short log form of a URL: path plus the parameters that identify the page."""
    parts = urlsplit(url)
    keep = []
    for key in ("baseClass", "cmdClass", "cmd", "ref_id", "ass_id", "mode"):
        value = parsers.query_param(url, key)
        if value:
            keep.append(f"{key}={value}")
    return parts.path + (("?" + "&".join(keep)) if keep else "")


class IliasClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        password_provider: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.policy = ReadOnlyPolicy(settings.host)
        self._password_provider = password_provider or (
            lambda: keychain_password(settings.keychain_service, settings.username)
        )
        guard = GuardedTransport(
            transport or httpx.HTTPTransport(retries=1),
            self.policy,
            settings.min_interval,
            sleep=sleep,
            clock=clock,
            on_request=self._count,
        )
        self.http = httpx.Client(
            transport=guard,
            follow_redirects=True,
            timeout=settings.timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": f"{settings.lang},en;q=0.8"},
        )
        self._lock = threading.RLock()
        self.logged_in = False
        self._login_blocked: str | None = None
        self.requests_total = 0
        self._call_requests = 0
        self._call_limit: int | None = None

    # -- bookkeeping ---------------------------------------------------------

    @contextmanager
    def call_scope(self, limit: int | None = None) -> Iterator[None]:
        """One tool call: serialized, with its own request budget."""
        with self._lock:
            self._call_requests = 0
            self._call_limit = limit or self.settings.max_requests_per_call
            try:
                yield
            finally:
                self._call_limit = None

    @property
    def call_requests(self) -> int:
        return self._call_requests

    def budget_left(self) -> int:
        if self._call_limit is None:
            return 10**6
        return self._call_limit - self._call_requests

    def _count(self, request: httpx.Request) -> None:
        self.requests_total += 1
        self._call_requests += 1
        if self._call_limit is not None and self._call_requests > self._call_limit:
            raise BudgetExceeded(
                f"request budget of {self._call_limit} for this call used up; "
                "narrow the request (lower depth, one course at a time)"
            )

    def absolute(self, url: str) -> str:
        return urljoin(self.settings.base_url + "/", url)

    def close(self) -> None:
        self.http.close()

    # -- login ---------------------------------------------------------------

    def login(self) -> None:
        with self._lock:
            if self._login_blocked:
                raise LoginError(self._login_blocked)
            resp = self.http.get(self.settings.login_url)
            if parsers.is_logged_in(resp.text):
                self.logged_in = True
                return
            form = parsers.find_login_form(resp.text, str(resp.url))
            if form is None:
                reason = (
                    "ILIAS only offers Shibboleth/SSO login here, which this client does not support"
                    if parsers.has_shibboleth_login(resp.text)
                    else f"no login form found at {_describe(str(resp.url))}"
                )
                self._block(reason)
            data = dict(form.fields)
            data[form.user_field] = self.settings.username
            data[form.password_field] = self._password_provider()
            try:
                with self.policy.login_window(form.action):
                    resp = self.http.post(form.action, data=data)
            except PolicyViolation as exc:
                self._block(
                    f"ILIAS showed an unexpected page right after login ({exc}). "
                    "Log in once in the browser and deal with any prompt (terms of use, "
                    "profile update), then restart this server."
                )
            finally:
                data.clear()
            if parsers.is_logged_in(resp.text):
                self.logged_in = True
                log.info("logged in as %s", self.settings.username)
                return
            if parsers.is_login_page(resp.text):
                self._block(
                    "ILIAS rejected the username or password. Not retrying, to avoid an "
                    "account lockout. Fix the Keychain item, then restart the server."
                )
            check = self.http.get(self.settings.dashboard_url)
            if parsers.is_logged_in(check.text):
                self.logged_in = True
                return
            self._block("login did not reach a logged-in ILIAS page; not retrying")

    def _block(self, reason: str) -> None:
        self._login_blocked = reason
        self.logged_in = False
        raise LoginError(reason)

    @staticmethod
    def _looks_logged_out(resp: httpx.Response) -> bool:
        if "html" not in resp.headers.get("content-type", "").lower():
            return False
        if urlsplit(str(resp.url)).path.endswith("/login.php"):
            return True
        return parsers.is_login_page(resp.text)

    # -- fetching ------------------------------------------------------------

    def get_page(self, url: str) -> Page:
        url = self.absolute(url)
        with self._lock:
            if not self.logged_in:
                self.login()
            resp = self.http.get(url)
            if self._looks_logged_out(resp):
                self.logged_in = False
                self.login()
                resp = self.http.get(url)
                if self._looks_logged_out(resp):
                    raise LoginError("still on the login page after logging in again")
            _raise_for_status(resp)
            return Page(str(resp.url), resp.text)

    def get_file(self, urls: list[str]) -> FileDownload:
        """Download the first URL that yields a file (not an HTML page)."""
        errors: list[str] = []
        with self._lock:
            if not self.logged_in:
                self.login()
            for raw in urls:
                url = self.absolute(raw)
                for attempt in (1, 2):
                    try:
                        result = self._download(url)
                    except _LoggedOut:
                        if attempt == 2:
                            raise LoginError("download keeps returning the login page") from None
                        self.logged_in = False
                        self.login()
                        continue
                    except (IliasError, PolicyViolation) as exc:
                        errors.append(f"{_describe(url)}: {exc}")
                        break
                    if result is not None:
                        return result
                    errors.append(f"{_describe(url)}: returned an HTML page, not a file")
                    break
        raise IliasError("could not download the file. " + " | ".join(errors))

    def _download(self, url: str) -> FileDownload | None:
        limit = self.settings.max_file_bytes
        with self.http.stream("GET", url) as resp:
            ctype = resp.headers.get("content-type", "")
            if resp.status_code >= 400:
                raise IliasError(f"HTTP {resp.status_code}")
            if "text/html" in ctype.lower():
                html = resp.read()[:2_000_000].decode(resp.encoding or "utf-8", "replace")
                if urlsplit(str(resp.url)).path.endswith("/login.php") or parsers.is_login_page(html):
                    raise _LoggedOut()
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > limit:
                    raise IliasError(f"file larger than {limit // (1024 * 1024)} MB; not downloaded")
                chunks.append(chunk)
            return FileDownload(
                url=str(resp.url),
                content=b"".join(chunks),
                filename=_filename(resp.headers.get("content-disposition", "")),
                content_type=ctype,
            )


class _LoggedOut(Exception):
    pass


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise IliasError(f"HTTP {resp.status_code} for {_describe(str(resp.url))}")


def _filename(disposition: str) -> str | None:
    match = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", disposition, re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r'filename\s*=\s*"?([^";]+)"?', disposition, re.I)
    return match.group(1).strip() if match else None
