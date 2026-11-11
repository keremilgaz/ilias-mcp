"""Read and write ILIAS passwords in the operating system credential store."""

from __future__ import annotations

import sys


class CredentialError(RuntimeError):
    pass


class PasswordMissing(CredentialError):
    pass


def store_hint(service: str, account: str) -> str:
    # Keep the old terminal commands usable for users with a manual setup.
    if sys.platform == "darwin":
        return f"security add-generic-password -s {service} -a {account} -w"
    python = r".venv\Scripts\python" if sys.platform == "win32" else ".venv/bin/python"
    return f"{python} -m keyring set {service} {account}"


def _keyring_call(method: str, *args: str) -> str | None:
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError:
        raise CredentialError("The credential store dependency is missing. Reinstall ilias-mcp.") from None
    try:
        return getattr(keyring, method)(*args)
    except (KeyringError, OSError, RuntimeError, ValueError):
        hint = (
            " Start or unlock a Secret Service keyring in your Linux user session."
            if sys.platform.startswith("linux")
            else " Unlock Windows Credential Manager and try again."
        )
        raise CredentialError("The system credential store is not available." + hint) from None


def _macos_keychain(service: str, account: str, password: str | None = None) -> str | None:
    try:
        import Security
    except ImportError:
        raise CredentialError("The macOS Keychain dependency is missing. Reinstall ilias-mcp.") from None
    query = {
        Security.kSecClass: Security.kSecClassGenericPassword,
        Security.kSecAttrService: service,
        Security.kSecAttrAccount: account,
    }
    if password is None:
        status, value = Security.SecItemCopyMatching({**query, Security.kSecReturnData: True}, None)
        if status == Security.errSecSuccess:
            return bytes(value).decode("utf-8")
        if status == Security.errSecItemNotFound:
            return None
    else:
        value = {Security.kSecValueData: password.encode("utf-8")}
        status, _ = Security.SecItemAdd({**query, **value}, None)
        if status == Security.errSecDuplicateItem:
            status = Security.SecItemUpdate(query, value)
        if status == Security.errSecSuccess:
            return None
    raise CredentialError(f"macOS Keychain returned error {status}. Unlock the login keychain and try again.")


def keychain_password(service: str, account: str) -> str:
    if sys.platform == "darwin":
        password = _macos_keychain(service, account)
    else:
        password = _keyring_call("get_password", service, account)
    if not password:
        raise PasswordMissing(
            f"No saved password for {account!r}. Run ilias-mcp-config setup, or use: {store_hint(service, account)}"
        )
    return password


def save_password(service: str, account: str, password: str) -> None:
    if not password:
        raise CredentialError("Enter your ILIAS password.")
    if sys.platform == "darwin":
        _macos_keychain(service, account, password)
    else:
        _keyring_call("set_password", service, account, password)
