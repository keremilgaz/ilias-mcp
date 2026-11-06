from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from ilias_mcp.client import IliasClient
from ilias_mcp.config import Settings
from ilias_mcp.files import FileCache
from ilias_mcp.service import IliasService

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://ilias.uni-konstanz.de"
PASSWORD = "correct horse battery staple"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


def make_pdf(pages: list[str]) -> bytes:
    canvas_mod = pytest.importorskip("reportlab.pdfgen.canvas")
    buffer = io.BytesIO()
    canvas = canvas_mod.Canvas(buffer)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            canvas.drawString(72, y, line)
            y -= 16
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def make_pptx(slides: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        for n, text in enumerate(slides, 1):
            archive.writestr(
                f"ppt/slides/slide{n}.xml",
                f'<p:sld xmlns:a="a" xmlns:p="p"><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>',
            )
    return buffer.getvalue()


class FakeIlias:
    """Just enough of ILIAS to exercise the client: login, redirects, pages, files."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sessions: set[str] = set()
        self.login_posts = 0
        self.files: dict[str, tuple[bytes, str]] = {}
        self.fail_when = None  # optional predicate: answer matching requests with 404
        self.pages = {
            ("/ilias.php", "ildashboardgui", "jumptoselecteditems"): "dashboard.html",
            ("/ilias.php", "ildashboardgui", ""): "news.html",
            ("/ilias.php", "ilrepositorygui", "view"): None,  # by ref_id
        }
        self.ref_pages = {
            "2125765": "course.html",
            "2131737": "folder.html",
            "2131742": "forum.html",
            "2131760": "session.html",
            "2099965": "folder.html",
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_when is not None and self.fail_when(request):
            return httpx.Response(404)
        url = request.url
        path = url.path
        q = {k.lower(): v[0] for k, v in parse_qs(urlsplit(str(url)).query).items()}
        cookie = request.headers.get("cookie", "")
        logged_in = any(f"PHPSESSID={s}" in cookie for s in self.sessions)

        if path == "/login.php":
            return self.html(fixture("login.html"))
        if request.method == "POST":
            self.login_posts += 1
            body = parse_qs(request.content.decode())
            if body.get("login_form/input_3/input_5") == [PASSWORD] and body.get(
                "login_form/input_3/input_4"
            ) == ["max.mustermann"]:
                sid = f"s{len(self.sessions) + 1}"
                self.sessions.add(sid)
                return httpx.Response(
                    303,
                    headers={
                        "location": "/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems",
                        "set-cookie": f"PHPSESSID={sid}; Path=/; Secure",
                    },
                )
            return self.html(fixture("login.html"))
        if not logged_in:
            return self.html(fixture("login.html"))  # ILIAS answers 200 with the login page

        if path.startswith("/goto.php/"):
            kind, ref = path.split("/")[2:4]
            if kind == "file":
                return self.file(ref)
            if kind == "exc":
                return self.redirect(
                    "/ilias.php?baseClass=ilexercisehandlergui&cmdNode=dw:on&cmdClass=ilObjExerciseGUI"
                    f"&cmd=showOverview&ref_id={ref}"
                )
            if kind == "trap":
                return self.redirect(f"/ilias.php?baseClass=ilrepositorygui&cmd=leave&ref_id={ref}")
            gui = {"crs": "ilobjcoursegui", "fold": "ilobjfoldergui", "frm": "ilObjForumGUI",
                   "sess": "ilobjsessiongui", "grp": "ilobjgroupgui"}.get(kind, "ilobjgui")
            return self.redirect(f"/ilias.php?baseClass=ilrepositorygui&cmdNode=zb:p1&cmdClass={gui}&ref_id={ref}")
        base_class = q.get("baseclass", "").lower()
        cmd = q.get("cmd", "").lower()
        if cmd == "sendfile":
            return self.file(q["ref_id"])
        if base_class == "ilexercisehandlergui":
            name = "exercise_all.html" if q.get("mode") == "all" else "exercise_default.html"
            return self.html(fixture(name))
        if base_class == "ildashboardgui" and q.get("cmdclass", "").lower() == "ilpdnewsgui":
            return self.html(fixture("news.html"))
        if base_class == "ildashboardgui":
            return self.html(fixture("dashboard.html"))
        if base_class == "ilrepositorygui" and q.get("ref_id") in self.ref_pages:
            return self.html(fixture(self.ref_pages[q["ref_id"]]))
        return httpx.Response(404, text="not found")

    def file(self, ref: str) -> httpx.Response:
        if ref not in self.files:
            return httpx.Response(404)
        content, name = self.files[ref]
        return httpx.Response(
            200,
            content=content,
            headers={
                "content-type": "application/octet-stream",
                "content-disposition": f"attachment; filename*=UTF-8''{name}",
            },
        )

    @staticmethod
    def html(text: str) -> httpx.Response:
        return httpx.Response(200, text=text, headers={"content-type": "text/html; charset=utf-8"})

    @staticmethod
    def redirect(location: str) -> httpx.Response:
        return httpx.Response(302, headers={"location": location})

    def expire_sessions(self) -> None:
        self.sessions.clear()


@pytest.fixture
def fake() -> FakeIlias:
    return FakeIlias()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        username="max.mustermann",
        min_interval=1.0,
        cache_dir=tmp_path / "cache",
        download_root=tmp_path / "Uni",
    )


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def client(fake: FakeIlias, settings: Settings, sleeps: list[float]) -> IliasClient:
    clock = {"t": 0.0}

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    return IliasClient(
        settings,
        transport=httpx.MockTransport(fake),
        password_provider=lambda: PASSWORD,
        sleep=sleep,
        clock=lambda: clock["t"],
    )


@pytest.fixture
def service(client: IliasClient, settings: Settings) -> IliasService:
    return IliasService(settings, client, FileCache(settings.cache_dir / "files"))
