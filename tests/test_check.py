import json
import sys

import httpx
import pytest

from ilias_mcp import check
from ilias_mcp.client import IliasClient

from .conftest import PASSWORD


def test_selftest_report_and_redacted_dump(fake, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ILIAS_USER", "max.mustermann")
    monkeypatch.setenv("ILIAS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(
        check,
        "IliasClient",
        lambda settings: IliasClient(settings, transport=httpx.MockTransport(fake),
                                     password_provider=lambda: PASSWORD, sleep=lambda s: None),
    )
    report_path = tmp_path / "report.json"
    dump = tmp_path / "pages"
    monkeypatch.setattr(sys, "argv", ["ilias-mcp-check", "--report", str(report_path), "--dump", str(dump)])
    with pytest.raises(SystemExit) as done:
        check.main()
    assert done.value.code == 0
    report = json.loads(report_path.read_text("utf-8"))
    assert [s["step"] for s in report["steps"]][:2] == ["list_courses", "list_items crs/2125765"]
    assert all(s["ok"] for s in report["steps"])
    dumped = "".join(p.read_text("utf-8") for p in dump.glob("*.html"))
    assert "rtoken=abc123" not in dumped and "rtoken=REDACTED" in dumped
    assert PASSWORD not in report_path.read_text("utf-8") + dumped
