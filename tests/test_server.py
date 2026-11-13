"""The MCP layer: tool registration, schemas and a round trip through call_tool."""

import json

import anyio
import pytest

from ilias_mcp import server
from ilias_mcp.service import IliasService

from .conftest import make_pdf

EXPECTED = {
    "ilias_status", "ilias_list_courses", "ilias_list_items", "ilias_page_text",
    "ilias_list_assignments", "ilias_read_file", "ilias_list_forum_topics",
    "ilias_list_news", "ilias_scan", "ilias_commit_scan", "ilias_download_file",
    "ilias_check_all", "ilias_card_preview", "ilias_card_decide",
}


@pytest.fixture
def mcp(service: IliasService):
    server.configure(service)
    yield server.mcp
    server.configure(None)  # type: ignore[arg-type]


def _payload(result) -> dict:
    if getattr(result, "structured_content", None):
        content = result.structured_content
        return content.get("result", content)
    return json.loads(result.content[0].text)


def test_tools_and_schemas(mcp) -> None:
    tools = {t.name: t for t in anyio.run(mcp.list_tools)}
    assert set(tools) == EXPECTED
    for tool in tools.values():
        assert "service" not in tool.input_schema.get("properties", {})
        assert tool.description
    reading = [n for n, t in tools.items() if t.annotations and t.annotations.read_only_hint]
    assert set(reading) == EXPECTED - {"ilias_card_decide"}
    assert tools["ilias_read_file"].input_schema["required"] == ["target"]
    for name in ("ilias_commit_scan", "ilias_download_file"):
        assert tools[name].meta["ui"]["resourceUri"] == "ui://ilias/approval.html"
        assert "ctx" not in tools[name].input_schema["properties"]
    assert tools["ilias_card_decide"].meta["ui"]["visibility"] == ["app"]
    assert tools["ilias_card_preview"].meta["ui"]["visibility"] == ["app"]


def test_call_tool_round_trip(mcp, fake) -> None:
    fake.files["2131745"] = (make_pdf(["Hello ILIAS"]), "org.pdf")
    result = anyio.run(mcp.call_tool, "ilias_read_file", {"target": "2131745"})
    data = _payload(result)
    assert data["text"][0]["text"] == "Hello ILIAS"


def test_errors_come_back_as_data(mcp) -> None:
    result = anyio.run(
        mcp.call_tool,
        "ilias_page_text",
        {"target": "https://ilias.uni-konstanz.de/ilias.php?baseClass=ilrepositorygui&cmd=leave&ref_id=1"},
    )
    data = _payload(result)
    assert "read-only policy" in data["error"]


def test_check_all_runs_in_background(mcp, service, monkeypatch) -> None:
    import threading
    release = threading.Event()
    real = service.check_all

    def slow(**kwargs):
        release.wait(5)
        return real(**kwargs)

    monkeypatch.setattr(service, "check_all", slow)
    server._job = None
    first = _payload(anyio.run(mcp.call_tool, "ilias_check_all", {"wait_seconds": 1}))
    assert first["status"] == "running"
    release.set()
    second = _payload(anyio.run(mcp.call_tool, "ilias_check_all", {"wait_seconds": 20}))
    assert "check_id" in second and second["semester"] == "Winter semester 2026"
    # The finished result is handed out once; the next call starts a fresh check.
    third = _payload(anyio.run(mcp.call_tool, "ilias_check_all", {"wait_seconds": 20}))
    assert third["check_id"] != second["check_id"]


def test_approval_cards_bind_local_changes_and_consume_the_token(mcp, service, fake) -> None:
    from types import SimpleNamespace

    from mcp.server.context import ServerRequestContext
    from mcp.server.mcpserver import Context
    from mcp.types import Implementation

    session = SimpleNamespace(client_capabilities=None, client_params=SimpleNamespace(
        client_info=Implementation(name="claude-desktop-3p", version="fixture"),
    ))
    ctx = Context(request_context=ServerRequestContext(
        session=session, lifespan_context=None, protocol_version="2025-11-25", method="tools/call",
    ), mcp_server=mcp)
    fake.files["2131745"] = (b"example", "example.txt")
    download = {"target": "2131745", "dest_dir": "fixture"}

    async def call(name, args):
        return await mcp.call_tool(name, args, ctx)

    async def review(name, args):
        result = await call(name, args)
        payload = _payload(result)
        assert payload["status"] == "approval_required"
        assert payload["approval_ref"] in result.content[0].text
        preview = await call("ilias_card_preview", {"approval_ref": payload["approval_ref"]})
        card = _payload(preview)
        assert json.loads(preview.content[0].text) == card
        assert card["token"] not in json.dumps(_payload(result))
        assert card["token"] not in result.content[0].text
        return card

    async def decide(card, decision):
        return _payload(await call("ilias_card_decide", {"token": card["token"], "decision": decision}))

    async def verify():
        destination = service.settings.download_root / "fixture" / "example.txt"
        card = await review("ilias_download_file", download)
        assert not fake.requests and not destination.exists()
        assert (await decide(card, "decline"))["status"] == "declined"
        assert (await decide(card, "approve"))["status"] == "approval_expired"
        assert not fake.requests and not destination.exists()
        card = await review("ilias_download_file", download)
        assert (await decide(card, "approve"))["status"] == "saved"
        assert destination.read_bytes() == b"example"
        assert (await decide(card, "approve"))["status"] == "approval_expired"

        scan = service.scan("crs/2125765")
        scan_id = scan["scan_id"]
        path = service.pending_scan_path(scan_id)
        original = path.read_text("utf-8")
        card = await review("ilias_commit_scan", {"scan_id": scan_id})
        assert path.is_file()
        path.write_text(original + "\n", "utf-8")
        assert (await decide(card, "approve"))["status"] == "stale"
        assert path.is_file()
        card = await review("ilias_commit_scan", {"scan_id": scan_id})
        assert (await decide(card, "approve"))["status"] == "committed"
        assert not path.exists()

    anyio.run(verify)
