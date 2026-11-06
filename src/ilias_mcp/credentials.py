"""Password lookup. The password lives in the macOS Keychain, never in config.

Store it once (the command prompts for the password, so it never appears in
shell history):

    security add-generic-password -s ilias-mcp -a firstname.lastname -w
"""

from __future__ import annotations

import subprocess
import sys


class CredentialError(RuntimeError):
    pass


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
                f"Create it with: security add-generic-password -s {service} -a {account} -w"
            )
        password = result.stdout.rstrip("\n")
    else:  # other platforms: optional `keyring` package
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError:
            raise CredentialError("install the 'keyring' package or run on macOS") from None
        password = keyring.get_password(service, account) or ""
    if not password:
        raise CredentialError(f"Keychain item {service!r}/{account!r} is empty")
    return password
