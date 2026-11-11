"""Run ILIAS for ChatGPT using OpenAI's Secure MCP Tunnel."""

from __future__ import annotations

import argparse
import getpass
import os
import shlex
import shutil
import subprocess
import sys
import warnings

from . import __version__
from .config import AccountNotConfigured, ConfigError, load_settings
from .credentials import CredentialError, PasswordMissing, keychain_password
from .install import open_account_setup, server_command
from .setup_web import SetupError

DOWNLOAD_URL = "https://github.com/openai/tunnel-client/releases/latest"
TUNNELS_URL = "https://platform.openai.com/settings/organization/tunnels"
PLUGINS_URL = "https://chatgpt.com/plugins"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ilias-mcp-chatgpt", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--tunnel-client", metavar="PATH", help="path to the official tunnel-client executable")
    parser.add_argument("--tunnel-id", help="OpenAI tunnel ID (defaults to CONTROL_PLANE_TUNNEL_ID or prompts)")
    args = parser.parse_args(argv)

    executable = shutil.which(args.tunnel_client or "tunnel-client")
    if executable is None:
        print(f"Download and extract tunnel-client from {DOWNLOAD_URL}\n"
              "Add it to PATH or pass its path with --tunnel-client.", file=sys.stderr)
        return 1

    try:
        tunnel_id = args.tunnel_id or os.environ.get("CONTROL_PLANE_TUNNEL_ID")
        if not tunnel_id:
            print(f"Create or find your tunnel at {TUNNELS_URL}")
            tunnel_id = input("OpenAI tunnel ID: ").strip()
        if not tunnel_id.startswith("tunnel_"):
            raise SetupError("Enter the tunnel ID starting with tunnel_ from your OpenAI tunnel settings.")

        key = os.environ.get("CONTROL_PLANE_API_KEY")
        if not key:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass("OpenAI tunnel runtime API key: ").strip()
        if not key:
            raise SetupError("An OpenAI tunnel runtime API key is required.")

        try:
            settings = load_settings()
            keychain_password(settings.keychain_service, settings.username)
        except (AccountNotConfigured, PasswordMissing):
            open_account_setup()

        # tunnel-client parses this value into argv itself, including on Windows.
        command = [executable, "run", "--control-plane.tunnel-id", tunnel_id,
                   "--mcp.command", shlex.join(server_command()), "--health.listen-addr", "127.0.0.1:0"]
        print(f"In {PLUGINS_URL}, select Add custom MCP server → Tunnel and enter {tunnel_id}.", flush=True)
        print("Keep this terminal open while using ILIAS. Press Ctrl+C to stop the tunnel.", flush=True)
        return subprocess.run(command, env={**os.environ, "CONTROL_PLANE_API_KEY": key}, check=False).returncode
    except (KeyboardInterrupt, EOFError):
        return 130
    except getpass.GetPassWarning:
        print("Use an interactive terminal or set CONTROL_PLANE_API_KEY before starting the tunnel.", file=sys.stderr)
        return 1
    except (SetupError, ConfigError, CredentialError, OSError, ValueError) as exc:
        print(f"ChatGPT setup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
