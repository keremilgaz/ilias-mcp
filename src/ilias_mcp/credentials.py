"""Password lookup. The password lives in the system's credential store, never in config.

macOS: the Keychain, read with the built-in `security` tool. Store it once (the
command prompts for the password, so it never appears in shell history):

    security add-generic-password -s ilias-mcp -a firstname.lastname -w

Windows and Linux: the `keyring` package (Windows Credential Manager, or the
Secret Service on Linux). Store it once with:

    .venv\\Scripts\\python -m keyring set ilias-mcp firstname.lastname     (Windows)
    .venv/bin/python -m keyring set ilias-mcp firstname.lastname          (Linux)
"""

from __future__ import annotations

import subprocess
import sys


class CredentialError(RuntimeError):
    pass


def store_hint(service: str, account: str) -> str:
    """The command that saves the password on this platform."""
    if sys.platform == "darwin":
        return f"security add-generic-password -s {service} -a {account} -w"
    python = r".venv\Scripts\python" if sys.platform == "win32" else ".venv/bin/python"
    return f"{python} -m keyring set {service} {account}"


def keychain_password(service: str, account: str) -> str:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CredentialError(f"could not run the macOS security tool: {exc}") from None
        if result.returncode != 0:
            raise CredentialError(
                f"no Keychain item for service {service!r}, account {account!r}. "
                f"Create it with: {store_hint(service, account)}"
            )
        password = result.stdout.rstrip("\n")
    else:  # Windows Credential Manager / Linux Secret Service via `keyring`
        try:
            import keyring  # type: ignore[import-not-found]
            from keyring.errors import KeyringError  # type: ignore[import-not-found]
        except ImportError:
            raise CredentialError("the 'keyring' package is missing; run: pip install keyring") from None
        try:
            password = keyring.get_password(service, account) or ""
        except KeyringError as exc:
            raise CredentialError(f"the system credential store is not available: {exc}") from None
        if not password:
            raise CredentialError(
                f"no saved password for service {service!r}, account {account!r}. "
                f"Save it with: {store_hint(service, account)}"
            )
    if not password:
        raise CredentialError(f"the saved password for {service!r}/{account!r} is empty")
    return password
