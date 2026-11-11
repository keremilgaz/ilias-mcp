import json
import sys
import types
from pathlib import Path

import pytest

from ilias_mcp import credentials, install

CONFIG = "claude_desktop_config.json"


def test_config_paths(tmp_path) -> None:
    assert install.claude_config_paths("darwin", {}, tmp_path) == [
        tmp_path / "Library" / "Application Support" / "Claude" / CONFIG]
    assert install.claude_config_paths("linux", {}, tmp_path) == [tmp_path / ".config" / "Claude" / CONFIG]

    env = {"APPDATA": str(tmp_path / "Roaming"), "LOCALAPPDATA": str(tmp_path / "Local")}
    regular = tmp_path / "Roaming" / "Claude" / CONFIG
    assert install.claude_config_paths("win32", env, tmp_path) == [regular]  # nothing installed yet

    package = tmp_path / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc"
    package.mkdir(parents=True)  # Microsoft Store / MSIX install
    packaged = package / "LocalCache" / "Roaming" / "Claude" / CONFIG
    assert install.claude_config_paths("win32", env, tmp_path) == [packaged]

    regular.parent.mkdir(parents=True)  # both installers were used at some point
    assert install.claude_config_paths("win32", env, tmp_path) == [packaged, regular]


def test_server_command(tmp_path) -> None:
    (tmp_path / "ilias-mcp.exe").touch()
    assert install.server_command(tmp_path, "win32") == [str(tmp_path / "ilias-mcp.exe")]
    (tmp_path / "ilias-mcp").touch()
    assert install.server_command(tmp_path, "darwin") == [str(tmp_path / "ilias-mcp")]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert install.server_command(empty, "linux")[1:] == ["-m", "ilias_mcp.server"]


def test_merge_keeps_other_servers_and_backs_up(tmp_path) -> None:
    path = tmp_path / CONFIG
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}), "utf-8")
    command = [r"C:\Users\max\ilias-mcp\.venv\Scripts\ilias-mcp.exe"]
    result = install.merge_config(path, "max.mustermann", r"D:\ILIAS", command)
    assert result["status"] == "updated" and Path(result["backup"]).exists()
    data = json.loads(path.read_text("utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["ilias"] == {
        "command": command[0], "env": {"ILIAS_USER": "max.mustermann", "ILIAS_DOWNLOAD_ROOT": r"D:\ILIAS"}}

    again = install.merge_config(path, "max.mustermann", r"D:\ILIAS", command)
    assert again["status"] == "unchanged"
    assert len(list(tmp_path.glob("*.bak-*"))) == 1  # no second backup for a no-op


def test_merge_keeps_extra_settings_and_reads_bom(tmp_path) -> None:
    path = tmp_path / CONFIG
    old = {"mcpServers": {"ilias": {"command": "old", "env": {"ILIAS_USER": "old", "ILIAS_MIN_INTERVAL": "2"}}}}
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(old).encode())  # as saved by Notepad
    install.merge_config(path, "new.user", None, ["/venv/bin/python", "-m", "ilias_mcp.server"])
    assert json.loads(path.read_text("utf-8"))["mcpServers"]["ilias"] == {
        "command": "/venv/bin/python",
        "args": ["-m", "ilias_mcp.server"],
        "env": {"ILIAS_USER": "new.user", "ILIAS_MIN_INTERVAL": "2"},
    }


def test_merge_refuses_broken_json(tmp_path) -> None:
    path = tmp_path / CONFIG
    path.write_text("{ not json", "utf-8")
    with pytest.raises(install.ConfigError):
        install.merge_config(path, "u", None, ["x"])
    assert path.read_text("utf-8") == "{ not json"
    assert not list(tmp_path.glob("*.bak-*"))


def test_cli_add_and_dry_run(tmp_path, capsys) -> None:
    path = tmp_path / "Claude" / CONFIG
    with pytest.raises(SystemExit) as done:
        install.main(["add", "--user", "u", "--config", str(path), "--dry-run"])
    assert done.value.code == 0 and not path.exists()
    assert '"ILIAS_USER": "u"' in capsys.readouterr().out

    with pytest.raises(SystemExit) as done:
        install.main(["add", "--user", "u", "--download-root", str(tmp_path / "dl"), "--config", str(path)])
    assert done.value.code == 0
    entry = json.loads(path.read_text("utf-8"))["mcpServers"]["ilias"]
    assert entry["env"] == {"ILIAS_USER": "u", "ILIAS_DOWNLOAD_ROOT": str(tmp_path / "dl")}


def _fake_keyring(monkeypatch, stored: dict | None = None, error: str | None = None) -> None:
    """A stand-in for the keyring package, as used on Windows and Linux."""
    errors = types.ModuleType("keyring.errors")

    class KeyringError(Exception):
        pass

    errors.KeyringError = KeyringError  # type: ignore[attr-defined]
    module = types.ModuleType("keyring")

    def get_password(service: str, account: str) -> str | None:
        if error:
            raise KeyringError(error)
        return (stored or {}).get((service, account))

    module.get_password = get_password  # type: ignore[attr-defined]
    module.errors = errors  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", module)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors)
    monkeypatch.setattr(sys, "platform", "win32")


def test_keyring_password(monkeypatch) -> None:
    _fake_keyring(monkeypatch, {("ilias-mcp", "u"): "secret"})
    assert credentials.keychain_password("ilias-mcp", "u") == "secret"
    with pytest.raises(credentials.CredentialError, match="keyring set ilias-mcp other"):
        credentials.keychain_password("ilias-mcp", "other")


def test_keyring_without_backend(monkeypatch) -> None:
    _fake_keyring(monkeypatch, error="no recommended backend")
    with pytest.raises(credentials.CredentialError, match="not available"):
        credentials.keychain_password("ilias-mcp", "u")


def test_has_password_never_prints_it(monkeypatch, capsys) -> None:
    _fake_keyring(monkeypatch, {("ilias-mcp", "u"): "secret"})
    with pytest.raises(SystemExit) as done:
        install.main(["has-password", "--user", "u"])
    assert done.value.code == 0 and "secret" not in capsys.readouterr().out
    with pytest.raises(SystemExit) as done:
        install.main(["has-password", "--user", "nobody"])
    assert done.value.code == 1
