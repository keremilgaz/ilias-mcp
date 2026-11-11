"""The short-lived browser form used by ilias-mcp-config setup."""

from __future__ import annotations

import secrets
import sys
import threading
import time
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs


class SetupError(RuntimeError):
    pass


def _page(body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set up ILIAS MCP</title>
<style>
  :root {{ color-scheme: light dark; font: 1rem Inter, system-ui, sans-serif; }}
  body {{ max-width: 29rem; margin: clamp(2rem, 10vh, 6rem) auto; padding: 0 1.25rem; }}
  h1 {{ font-size: 1.75rem; }}
  label {{ display: block; margin-top: 1.25rem; font-weight: 600; }}
  input, button {{ box-sizing: border-box; font: inherit; padding: .65rem; border-radius: .35rem; }}
  input {{ display: block; width: 100%; margin-top: .35rem; border: 1px solid GrayText; }}
  button {{ margin-top: 1rem; padding-inline: 1rem; cursor: pointer; }}
  small {{ display: block; margin-top: .35rem; }}
  [role="alert"] {{ border: 1px solid currentColor; padding: .75rem; }}
</style>
<main><h1>Set up ILIAS MCP</h1>{body}</main>
</html>""".encode("utf-8")


def browser_setup(
    username: str, ilias_url: str, save: Callable[[str, str], None], timeout: float = 600
) -> str:
    route = "/" + secrets.token_urlsafe(32)
    lock = threading.Lock()
    account: str | None = None
    deadline = time.monotonic() + timeout

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *_args: object) -> None:
            pass  # No request paths or form data in the terminal.

        def reply(self, status: int, body: str) -> None:
            content = _page(body)
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'; base-uri 'none'",
            )
            try:
                self.end_headers()
                self.wfile.write(content)
            except (ConnectionError, TimeoutError):
                pass

        def valid_route(self) -> bool:
            if self.path == route and self.headers.get_all("Host") == [host]:
                return True
            self.reply(404, "<p>Setup page not found.</p>")
            return False

        def form(self, user: str, error: str = "") -> None:
            alert = f'<p role="alert">{escape(error)}</p>' if error else ""
            self.reply(400 if error else 200, f"""
<p>Enter your account for <strong>{escape(ilias_url)}</strong>.
Your password is stored in your system credential store.</p>
{alert}
<form method="post" action="{route}">
  <label for="user">ILIAS username</label>
  <input id="user" name="username" value="{escape(user, quote=True)}" autocomplete="username" required>
  <label for="password">ILIAS password</label>
  <input id="password" name="password" type="password" autocomplete="off" aria-describedby="password-hint">
  <small id="password-hint">Leave blank to keep a password you already saved.</small>
  <button type="submit">Save account</button>
</form>""")

        def do_GET(self) -> None:
            if self.valid_route():
                self.form(username)

        def do_POST(self) -> None:
            nonlocal account
            if not self.valid_route():
                return
            if self.headers.get_all("Origin") != [origin]:
                self.reply(403, "<p>Open the setup address directly in your browser.</p>")
                return
            try:
                sizes = self.headers.get_all("Content-Length") or []
                if len(sizes) != 1:
                    raise ValueError
                length = int(sizes[0])
                if (not 0 < length <= 8192
                        or self.headers.get("Transfer-Encoding")
                        or self.headers.get_content_type() != "application/x-www-form-urlencoded"):
                    raise ValueError
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError
                fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True,
                                  max_num_fields=2, errors="strict")
                user, = fields["username"]
                password, = fields["password"]
                user = user.strip()
            except (KeyError, ValueError, OSError):
                self.form(username, "The form could not be read. Please try again.")
                return
            with lock:
                if account is not None or time.monotonic() >= deadline:
                    self.reply(410, "<p>This setup session has ended.</p>")
                    return
                try:
                    save(user, password)
                except SetupError as exc:
                    self.form(user, str(exc))
                    return
                account = user
                self.reply(200, "<p>Account saved. You can close this tab.</p>")

    def open_browser(url: str) -> None:
        try:
            webbrowser.open(url)
        except (OSError, webbrowser.Error):
            pass  # The address is also printed for manual opening.

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 0.25
        host = f"127.0.0.1:{server.server_port}"
        origin = f"http://{host}"
        url = origin + route
        print(f"Open this address if your browser did not open automatically:\n{url}", file=sys.stderr, flush=True)
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
        while account is None and time.monotonic() < deadline:
            server.handle_request()
        # Allow an in-progress submission and its response to finish.
        with lock:
            if account is not None:
                return account
    raise SetupError("Browser setup timed out. Run setup again, or use --terminal.")
