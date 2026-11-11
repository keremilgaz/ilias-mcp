"""Settings, read from environment variables (set in the MCP client config)."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


def _default_cache_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ilias-mcp"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ilias-mcp" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ilias-mcp"


@dataclass(frozen=True)
class Settings:
    username: str
    base_url: str = "https://ilias.uni-konstanz.de"
    client_id: str = "ILIASKONSTANZ"
    lang: str = "en"
    keychain_service: str = "ilias-mcp"
    min_interval: float = 1.0
    timeout: float = 30.0
    max_requests_per_call: int = 60
    max_file_bytes: int = 60 * 1024 * 1024
    cache_dir: Path = _default_cache_dir()
    download_root: Path = Path.home() / "Documents" / "ILIAS"
    # File download route as used by the Konstanz installation (cmdNode values
    # are installation-specific); the generic goto.php route is tried after it.
    sendfile_template: str = (
        "/ilias.php?baseClass=ilrepositorygui&cmdNode=zb:ow&cmdClass=ilObjFileGUI"
        "&cmd=sendfile&ref_id={ref_id}"
    )

    @property
    def host(self) -> str:
        return self.base_url.split("://", 1)[-1].split("/", 1)[0]

    @property
    def login_url(self) -> str:
        return (
            f"{self.base_url}/login.php?client_id={self.client_id}"
            f"&cmd=force_login&lang={self.lang}"
        )

    @property
    def dashboard_url(self) -> str:
        return f"{self.base_url}/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems"

    @property
    def memberships_url(self) -> str:
        return f"{self.base_url}/ilias.php?baseClass=ilmembershipoverviewgui"

    @property
    def account_dir(self) -> Path:
        """Cache of this ILIAS installation and account: file texts, reading records,
        snapshots and routes are never shared between accounts."""
        slug = re.sub(r"[^a-z0-9._-]+", "_", f"{self.host}-{self.client_id}-{self.username}".lower())
        return Path(self.cache_dir) / "accounts" / slug


_LEGACY = ("files", "snapshots", "routes.json")  # cache layout before 0.3, one account per machine


def prepare_cache(settings: Settings) -> Path:
    """Create the account's cache folder. A cache from before 0.3 (kept directly in
    cache_dir, without an account) is moved into the first account that starts."""
    base, target = Path(settings.cache_dir), settings.account_dir
    if not target.exists():
        target.mkdir(parents=True)
        for name in _LEGACY:
            if (base / name).exists():
                (base / name).replace(target / name)
    return target


def load_settings() -> Settings:
    username = os.environ.get("ILIAS_USER", "").strip()
    if not username:
        raise SystemExit("ILIAS_USER is not set (your ILIAS login, e.g. firstname.lastname).")
    kwargs: dict = {"username": username}
    env_map = {
        "ILIAS_BASE_URL": ("base_url", str),
        "ILIAS_CLIENT_ID": ("client_id", str),
        "ILIAS_LANG": ("lang", str),
        "ILIAS_KEYCHAIN_SERVICE": ("keychain_service", str),
        "ILIAS_MIN_INTERVAL": ("min_interval", float),
        "ILIAS_TIMEOUT": ("timeout", float),
        "ILIAS_MAX_REQUESTS_PER_CALL": ("max_requests_per_call", int),
        "ILIAS_CACHE_DIR": ("cache_dir", Path),
        "ILIAS_DOWNLOAD_ROOT": ("download_root", Path),
    }
    for env, (field, cast) in env_map.items():
        raw = os.environ.get(env, "").strip()
        if raw:
            kwargs[field] = cast(os.path.expanduser(raw)) if cast is Path else cast(raw)
    if "base_url" in kwargs:
        kwargs["base_url"] = kwargs["base_url"].rstrip("/")
    settings = Settings(**kwargs)
    if settings.min_interval < 0.5:
        settings = Settings(**{**kwargs, "min_interval": 0.5})  # be gentle with ILIAS
    return settings
