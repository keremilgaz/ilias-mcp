"""Set up an ILIAS account and configure Claude Desktop or another MCP client.

Used by setup.sh (macOS and Linux) and setup.ps1 (Windows):

    ilias-mcp-config setup [--terminal] [--skip-check] [--no-claude]
    ilias-mcp-config add --user firstname.lastname [--download-root DIR] [--config FILE] [--dry-run]
    ilias-mcp-config has-password --user firstname.lastname
    ilias-mcp-config cache --user firstname.lastname [--adopt | --ask]

`add` keeps every other server and setting, makes a timestamped backup before
changing an existing file and refuses to touch a file that is not valid JSON.
`has-password` only reports whether a password is saved (exit code 0 or 1);
it never prints it. `cache` shows the account's cache folder; a cache from
version 0.2 or older records no account, so it is used only after `--adopt`
(or a yes to `--ask`) says it is this account's.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Mapping

import httpx

from . import __version__
from .client import IliasClient, IliasError
from .config import (
    ConfigError, adopt_legacy_cache, has_data, legacy_cache, load_settings,
    read_profile, save_profile, write_json,
)
from .credentials import CredentialError, keychain_password, save_password
from .policy import PolicyViolation
from .setup_web import SetupError, browser_setup

SERVER_NAME = "ilias"
CONFIG_NAME = "claude_desktop_config.json"


def claude_config_paths(
    platform: str = sys.platform,
    env: Mapping[str, str] = os.environ,
    home: Path | None = None,
) -> list[Path]:
    """Where the Claude desktop app reads its configuration on this system.

    Windows has two locations: the regular installer uses %APPDATA%\\Claude, the
    Microsoft Store / MSIX package reads a redirected copy under
    %LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Roaming\\Claude. Every
    location that belongs to an installed app is returned.
    """
    home = home or Path.home()
    if platform == "darwin":
        return [home / "Library" / "Application Support" / "Claude" / CONFIG_NAME]
    if platform == "win32":
        roaming = Path(env.get("APPDATA") or home / "AppData" / "Roaming") / "Claude"
        local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        packaged = sorted((local / "Packages").glob("Claude_*")) if (local / "Packages").is_dir() else []
        paths = [p / "LocalCache" / "Roaming" / "Claude" / CONFIG_NAME for p in packaged]
        if roaming.is_dir() or not paths:
            paths.append(roaming / CONFIG_NAME)
        return paths
    return [Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "Claude" / CONFIG_NAME]


def server_command(scripts_dir: Path | None = None, platform: str = sys.platform) -> list[str]:
    """Command that starts the server from the current virtualenv.

    Not resolved: inside a virtualenv, sys.executable is a link into the
    environment and must stay that way.
    """
    scripts = scripts_dir or Path(sys.executable).absolute().parent
    exe = scripts / ("ilias-mcp.exe" if platform == "win32" else "ilias-mcp")
    if exe.exists():
        return [str(exe)]
    python = scripts / ("python.exe" if platform == "win32" else "python")
    return [str(python if python.exists() else Path(sys.executable).absolute()), "-m", "ilias_mcp.server"]


def server_entry(command: list[str], user: str, download_root: str | None,
                 previous: Mapping | None = None) -> dict:
    env = dict((previous or {}).get("env") or {})  # keep extra ILIAS_* settings the user added
    env["ILIAS_USER"] = user
    if download_root:
        env["ILIAS_DOWNLOAD_ROOT"] = download_root
    entry: dict = {"command": command[0]}
    if command[1:]:
        entry["args"] = command[1:]
    entry["env"] = env
    return entry


def merge_config(path: Path, user: str, download_root: str | None, command: list[str],
                 dry_run: bool = False) -> dict:
    """Add or update the server entry in one config file. Returns what happened."""
    data: dict = {}
    if path.exists():
        try:
            text = path.read_text("utf-8-sig").strip()  # Notepad may add a BOM
            data = json.loads(text) if text else {}
        except ValueError as exc:
            raise ConfigError(f"{path} is not valid JSON ({exc}); fix or move it, then try again") from None
        if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
            raise ConfigError(f"{path} has an unexpected structure; add the entry by hand (see --dry-run)")
    servers = data.setdefault("mcpServers", {})
    previous = servers.get(SERVER_NAME, {})
    if not isinstance(previous, dict) or (previous.get("env") is not None and not isinstance(previous["env"], dict)):
        raise ConfigError(f"{path} has an invalid {SERVER_NAME!r} entry. Fix or remove that entry and try again.")
    entry = server_entry(command, user, download_root, previous)
    result: dict = {"path": str(path), "entry": entry}
    if servers.get(SERVER_NAME) == entry:
        return {**result, "status": "unchanged"}
    if dry_run:
        return {**result, "status": "dry_run"}
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S-%f}")
        shutil.copy2(path, backup)
        result["backup"] = str(backup)
    servers[SERVER_NAME] = entry
    write_json(path, data)
    return {**result, "status": "updated" if result.get("backup") else "created"}


def _add(args: argparse.Namespace) -> int:
    paths = [Path(args.config).expanduser()] if args.config else claude_config_paths()
    command = server_command()
    root = str(Path(args.download_root).expanduser().absolute()) if args.download_root else None
    failed = False
    for path in paths:
        try:
            result = merge_config(path, args.user, root, command, dry_run=args.dry_run)
        except (ConfigError, OSError) as exc:
            print(f"   error: {exc}")
            failed = True
            continue
        if result["status"] == "dry_run":
            print(f"   Not changed. Put this under \"mcpServers\" in {path}:")
            print(json.dumps({SERVER_NAME: result["entry"]}, indent=2, ensure_ascii=False))
            continue
        if "backup" in result:
            print(f"   backup: {result['backup']}")
        print(f"   {result['status']}: {path}")
    return 1 if failed else 0


def _has_password(args: argparse.Namespace) -> int:
    try:
        keychain_password(args.service, args.user)
    except CredentialError as exc:
        print(f"   {exc}")
        return 1
    print("   A saved password exists.")
    return 0


def _save_account(username: str, password: str, download_root: str | None, verify: bool) -> None:
    if not username or any(ord(char) < 32 or ord(char) == 127 for char in username):
        raise SetupError("Enter a valid ILIAS username.")
    try:
        settings = load_settings(username)
        candidate = password or keychain_password(settings.keychain_service, username)
        if verify:
            client = IliasClient(settings, password_provider=lambda: candidate)
            try:
                client.login()
            finally:
                client.close()
        if password:
            save_password(settings.keychain_service, username, candidate)
        save_profile(username, download_root)
    except (ConfigError, CredentialError, IliasError, PolicyViolation, OSError, ValueError) as exc:
        raise SetupError(str(exc)) from None
    except httpx.HTTPError:
        raise SetupError("Could not reach ILIAS. Check your network and try again.") from None


def open_account_setup(username: str | None = None, download_root: str | None = None, *, verify: bool = True) -> str:
    """Open the local form and return the username once the account is saved."""
    user = _setup_username(username)
    ilias_url = load_settings(user or "setup").base_url

    def save(account: str, password: str) -> None:
        _save_account(account, password, download_root, verify=verify)

    return browser_setup(user, ilias_url, save)


def _setup_username(username: str | None) -> str:
    return (username or os.environ.get("ILIAS_USER") or "").strip() or read_profile().get("username", "")


def _setup(args: argparse.Namespace) -> int:
    def save(username: str, password: str) -> None:
        _save_account(username, password, args.download_root, verify=not args.skip_check)

    try:
        if args.terminal:
            user = _setup_username(args.user)
            prompt = f"ILIAS username [{user}]: " if user else "ILIAS username: "
            user = input(prompt).strip() or user
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("ILIAS password (leave blank to keep the saved password): ")
            save(user, password)
        else:
            user = open_account_setup(args.user, args.download_root, verify=not args.skip_check)
    except (KeyboardInterrupt, EOFError):
        print("Setup cancelled.", file=sys.stderr)
        return 1
    except getpass.GetPassWarning:
        print("Open an interactive terminal to enter your password, or run setup without --terminal.", file=sys.stderr)
        return 1
    except (ConfigError, SetupError, OSError, ValueError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Saved ILIAS account {user}.")
    if args.no_claude:
        print(f"MCP server command: {json.dumps(server_command(), ensure_ascii=False)}")
        return 0
    result = _add(argparse.Namespace(user=user, config=args.config, download_root=args.download_root, dry_run=False))
    if result == 0:
        print("Quit Claude Desktop completely and reopen it to load ILIAS.")
    return result


def _cache(args: argparse.Namespace) -> int:
    settings = load_settings(args.user)
    target = settings.account_dir
    if args.ask and not legacy_cache(settings):
        return 0  # setup: nothing to ask about
    state = "has saved data" if any(has_data(target / n) for n in ("files", "snapshots")) else "empty"
    print(f"   cache of {args.user}: {target} ({state})")
    accounts = Path(settings.cache_dir) / "accounts"
    others = sorted(p.name for p in accounts.iterdir() if p.is_dir() and p != target) if accounts.is_dir() else []
    if others:
        print(f"   other accounts on this computer: {', '.join(others)}")
    if not legacy_cache(settings):
        print("   no cache from an older version is waiting")
        return 0
    print(f"   A cache from version 0.2 or older was found in {settings.cache_dir}.")
    print("   It does not record whose account it was, so it is not used until you adopt it.")
    adopt = args.adopt
    if not adopt and args.ask:
        try:
            adopt = input(f"   Is it from {args.user}'s ILIAS account? [y/N] ").strip().lower().startswith(("y", "e"))
        except EOFError:
            adopt = False
    if not adopt:
        print(f"   To adopt it later: ilias-mcp-config cache --user {args.user} --adopt")
        return 0
    try:
        moved = adopt_legacy_cache(settings)
    except (ValueError, OSError) as exc:
        print(f"   error: {exc}")
        return 1
    print(f"   adopted into {target}: {', '.join(moved) or 'nothing to move'}")
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ilias-mcp-config", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="action", required=True)
    setup = sub.add_parser("setup", help="save your ILIAS login and configure your MCP client")
    setup.add_argument("--user", help="pre-fill your ILIAS username")
    setup.add_argument("--terminal", action="store_true", help="enter credentials in this terminal")
    setup.add_argument("--skip-check", action="store_true", help="save credentials without testing ILIAS login")
    setup.add_argument("--download-root", help="folder ilias_download_file may write to")
    client = setup.add_mutually_exclusive_group()
    client.add_argument("--no-claude", action="store_true", help="save the account for manual MCP client setup")
    client.add_argument("--config", help="Claude configuration file to update")
    add = sub.add_parser("add", help="add or update the ilias server in the Claude configuration")
    add.add_argument("--user", required=True, help="ILIAS login, e.g. firstname.lastname")
    add.add_argument("--download-root", help="folder ilias_download_file may write to")
    add.add_argument("--config", help="config file to change (default: the Claude desktop app's)")
    add.add_argument("--dry-run", action="store_true", help="print the entry instead of writing it")
    has = sub.add_parser("has-password", help="exit 0 if a password is saved for this user")
    has.add_argument("--user", required=True)
    has.add_argument("--service", default=os.environ.get("ILIAS_KEYCHAIN_SERVICE", "ilias-mcp"))
    cache = sub.add_parser("cache", help="show this account's cache; adopt a cache from version 0.2 or older")
    cache.add_argument("--user", required=True)
    mode = cache.add_mutually_exclusive_group()
    mode.add_argument("--adopt", action="store_true", help="the old cache is this account's: move it in")
    mode.add_argument("--ask", action="store_true", help="ask before adopting")
    args = ap.parse_args(argv)
    actions = {"setup": _setup, "add": _add, "has-password": _has_password, "cache": _cache}
    raise SystemExit(actions[args.action](args))


if __name__ == "__main__":
    main()
