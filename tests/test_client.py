import httpx
import pytest

from ilias_mcp.client import BudgetExceeded, IliasClient, IliasError, LoginError
from ilias_mcp.policy import PolicyViolation

from .conftest import PASSWORD


def test_logs_in_lazily_and_fetches(client: IliasClient, fake) -> None:
    page = client.get_page("/goto.php/crs/2125765")
    assert "Advances in Agentic AI" in page.html
    assert page.url.endswith("cmdClass=ilobjcoursegui&ref_id=2125765")
    assert fake.login_posts == 1
    assert client.logged_in


def test_relogs_in_when_session_expires(client: IliasClient, fake) -> None:
    client.get_page("/goto.php/crs/2125765")
    fake.expire_sessions()
    page = client.get_page("/goto.php/fold/2131737")
    assert "Lecture Content" in page.html
    assert fake.login_posts == 2


def test_wrong_password_is_not_retried(fake, settings) -> None:
    client = IliasClient(settings, transport=httpx.MockTransport(fake), password_provider=lambda: "wrong",
                         sleep=lambda s: None)
    with pytest.raises(LoginError) as first:
        client.get_page("/goto.php/crs/2125765")
    with pytest.raises(LoginError):
        client.get_page("/goto.php/crs/2125765")
    assert fake.login_posts == 1  # second call did not try again
    assert "wrong" not in str(first.value)


def test_temporary_login_page_failure_does_not_block_the_next_call(fake, settings) -> None:
    def respond(request):
        if not fake.requests:
            fake.requests.append(request)
            return httpx.Response(503)
        return fake(request)

    client = IliasClient(settings, transport=httpx.MockTransport(respond), password_provider=lambda: PASSWORD,
                         sleep=lambda _: None)
    with pytest.raises(IliasError, match="HTTP 503"):
        client.login()
    client.login()
    assert client.logged_in and fake.login_posts == 1


def test_password_never_appears_in_errors(fake, settings) -> None:
    client = IliasClient(settings, transport=httpx.MockTransport(fake), password_provider=lambda: PASSWORD,
                         sleep=lambda s: None)
    with pytest.raises(PolicyViolation) as exc:
        client.get_page("/goto.php/trap/1")
    assert PASSWORD not in str(exc.value)


def test_redirect_to_state_changing_url_is_blocked_before_sending(client: IliasClient, fake) -> None:
    with pytest.raises(PolicyViolation, match="leave"):
        client.get_page("/goto.php/trap/1")
    assert not any("cmd=leave" in str(r.url) for r in fake.requests)


def test_rtoken_links_are_never_requested(client: IliasClient, fake) -> None:
    client.get_page("/goto.php/crs/2125765")
    sent = len(fake.requests)
    with pytest.raises(PolicyViolation, match="rtoken"):
        client.get_page("/ilias.php?baseClass=ilDashboardGUI&cmd=removeFromDesk&ref_id=1&rtoken=abc")
    assert len(fake.requests) == sent


def test_only_get_is_sent_after_login(client: IliasClient, fake) -> None:
    client.get_page("/goto.php/crs/2125765")
    client.get_page("/goto.php/frm/2131742")
    methods = [r.method for r in fake.requests]
    assert methods.count("POST") == 1
    assert all(m == "GET" for m in methods if m != "POST")


def test_requests_are_spaced_out(client: IliasClient, sleeps) -> None:
    client.get_page("/goto.php/crs/2125765")
    assert sleeps and all(0 < s <= 1.0 for s in sleeps)


def test_budget_per_call(client: IliasClient) -> None:
    with pytest.raises(BudgetExceeded):
        with client.call_scope(limit=3):
            client.get_page("/goto.php/crs/2125765")  # login + redirect + page = 5 requests


def test_file_download_falls_back_to_second_route(client: IliasClient, fake) -> None:
    fake.files["7"] = (b"%PDF-1.4 fake", "a.pdf")
    download = client.get_file(["/ilias.php?baseClass=ilrepositorygui&cmd=view&ref_id=999", "/goto.php/file/7/download"])
    assert download.content.startswith(b"%PDF")
    assert download.filename == "a.pdf"
