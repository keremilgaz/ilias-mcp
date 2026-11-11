import json
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ilias_mcp import __version__, chatgpt
from ilias_mcp.config import AccountNotConfigured, Settings

ROOT = Path(__file__).resolve().parents[1]


def test_claude_bundle_starts_and_opens_browser_setup(tmp_path) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/build_mcpb.py"), "--output-dir", str(tmp_path)], check=True)
    unpacked = tmp_path / "Claude bundle"
    with ZipFile(tmp_path / f"ilias-mcp-{__version__}.mcpb") as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["version"] == __version__ and manifest["server"]["type"] == "uv"
        bundle.extractall(unpacked)

    entry = unpacked / manifest["server"]["entry_point"]
    address = tmp_path / "address.txt"
    bootstrap = f"""
import runpy
from pathlib import Path
from ilias_mcp import config, install, setup_web
config.profile_path = lambda: Path({str(tmp_path / 'settings.json')!r})
setup_web.webbrowser.open = lambda url: Path({str(address)!r}).write_text(url, 'utf-8')
install._save_account = lambda user, password, root, verify: config.save_profile(user, root)
runpy.run_path({str(entry)!r}, run_name='__main__')
"""
    params = StdioServerParameters(
        command=sys.executable, args=["-c", bootstrap], cwd=unpacked,
        env={"PYTHONPATH": str(unpacked / "src"), "ILIAS_USER": "", "ILIAS_CACHE_DIR": str(tmp_path / "cache")},
    )

    async def exercise_bundle() -> None:
        with anyio.fail_after(15):
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    result = await session.initialize()
                    assert result.server_info.version == __version__
                    tools = {tool.name for tool in (await session.list_tools()).tools}
                    assert {"ilias_setup", "ilias_list_courses", "ilias_status"} <= tools
                    status = await session.call_tool("ilias_status", {})
                    assert "ask to open ILIAS setup" in str(status)
                    result = await session.call_tool("ilias_setup", {})
                    assert "setup_started" in str(result)
                    while not address.exists() or not address.stat().st_size:
                        await anyio.sleep(0.05)
                    url = address.read_text("utf-8")
                    parts = urlsplit(url)
                    async with httpx.AsyncClient(trust_env=False) as browser:
                        response = await browser.post(url, data={"username": "claude.user", "password": "test-only"},
                                                      headers={"Origin": f"http://{parts.netloc}"})
                    assert response.status_code == 200
                    status = await session.call_tool("ilias_status", {})
                    assert "claude.user" in str(status)

    anyio.run(exercise_bundle)


def test_chatgpt_launcher_sets_up_missing_account_and_passes_key_through_environment(monkeypatch, capsys) -> None:
    def no_account():
        raise AccountNotConfigured

    events = []
    binary = r"C:\Some Folder\tunnel-client.exe"
    server = [r"C:\Users\Jane Doe\ilias-mcp.exe"]
    monkeypatch.setattr(chatgpt.shutil, "which", lambda name: binary)
    monkeypatch.setattr(chatgpt, "load_settings", no_account)
    monkeypatch.setattr(chatgpt, "open_account_setup", lambda: events.append("setup"))
    monkeypatch.setattr(chatgpt, "server_command", lambda: server)
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "test-runtime-key")

    def run(command, *, env, check):
        assert events == ["setup"]
        assert command[:4] == [binary, "run", "--control-plane.tunnel-id", "tunnel_example"]
        assert shlex.split(command[command.index("--mcp.command") + 1]) == server
        assert env["CONTROL_PLANE_API_KEY"] == "test-runtime-key"
        assert "test-runtime-key" not in str(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(chatgpt.subprocess, "run", run)
    assert chatgpt.main(["--tunnel-client", binary, "--tunnel-id", "tunnel_example"]) == 0
    assert "test-runtime-key" not in capsys.readouterr().out


def test_chatgpt_launcher_reuses_existing_account(monkeypatch) -> None:
    checked = []
    monkeypatch.setattr(chatgpt.shutil, "which", lambda name: "tunnel-client")
    monkeypatch.setattr(chatgpt, "load_settings", lambda: Settings(username="existing.user"))
    monkeypatch.setattr(chatgpt, "keychain_password", lambda service, user: checked.append((service, user)))
    monkeypatch.setattr(chatgpt, "open_account_setup", lambda: checked.append("unexpected setup"))
    monkeypatch.setattr(chatgpt.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    monkeypatch.setenv("CONTROL_PLANE_TUNNEL_ID", "tunnel_example")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "test-runtime-key")
    assert chatgpt.main([]) == 0
    assert checked == [("ilias-mcp", "existing.user")]
