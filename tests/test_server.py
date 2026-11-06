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
    assert set(reading) == EXPECTED - {"ilias_commit_scan", "ilias_download_file"}
    assert tools["ilias_read_file"].input_schema["required"] == ["target"]


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
