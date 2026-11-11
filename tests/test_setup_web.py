import socket
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from urllib.parse import urlsplit

import httpx

from ilias_mcp import setup_web


def test_browser_setup_accepts_only_its_form_and_does_not_echo_password(monkeypatch) -> None:
    def unexpected_lookup(*_args: object) -> str:
        raise AssertionError("The loopback server should start without reverse DNS")

    monkeypatch.setattr(socket, "getfqdn", unexpected_lookup)
    addresses: Queue[str] = Queue()
    monkeypatch.setattr(setup_web.webbrowser, "open", addresses.put)
    saved = []
    password = "sëcret & + <>"

    def save(user: str, candidate: str) -> None:
        if candidate != password:
            raise setup_web.SetupError("Try again <here>.")
        saved.append((user, candidate))

    with ThreadPoolExecutor() as executor:
        result = executor.submit(setup_web.browser_setup, 'old"user', "https://ilias.example", save, 8)
        url = addresses.get(timeout=3)
        parts = urlsplit(url)
        assert parts.hostname == "127.0.0.1"
        origin = f"http://{parts.netloc}"
        with httpx.Client(trust_env=False, timeout=3) as browser:
            form = browser.get(url)
            assert form.status_code == 200 and 'value="old&quot;user"' in form.text
            assert form.headers["cache-control"] == "no-store"
            assert browser.get(url, headers={"Host": "elsewhere.invalid"}).status_code == 404
            assert browser.get(origin + "/wrong").status_code == 404
            data = {"username": " new.user ", "password": password}
            assert browser.post(url, data=data, headers={"Origin": "https://elsewhere.invalid"}).status_code == 403
            assert not saved
            error = browser.post(url, data={**data, "password": "wrong-secret"}, headers={"Origin": origin})
            assert error.status_code == 400 and "Try again &lt;here&gt;." in error.text
            assert "wrong-secret" not in error.text
            done = browser.post(url, data=data, headers={"Origin": origin})
            assert done.status_code == 200 and "Account saved" in done.text and password not in done.text
        assert result.result(timeout=3) == "new.user"
    assert saved == [("new.user", password)]
