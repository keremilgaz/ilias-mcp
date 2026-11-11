"""Start the Claude Desktop bundle, with local browser account setup."""

import logging
import threading

from mcp.types import ToolAnnotations

from ilias_mcp import server
from ilias_mcp.config import ConfigError
from ilias_mcp.install import open_account_setup
from ilias_mcp.setup_web import SetupError

_setup_lock = threading.Lock()
_setup_thread: threading.Thread | None = None


def _run_setup() -> None:
    try:
        open_account_setup()
    except (ConfigError, SetupError, OSError, ValueError) as exc:
        logging.getLogger("ilias_mcp").warning("ILIAS setup failed: %s", exc)


def ilias_setup() -> dict:
    """Open the local ILIAS sign-in form when the user asks to set up or update their account."""
    global _setup_thread
    with _setup_lock:
        if _setup_thread is not None and _setup_thread.is_alive():
            return {"status": "setup_in_progress", "message": "Finish ILIAS setup in your browser."}
        _setup_thread = threading.Thread(target=_run_setup, daemon=True)
        _setup_thread.start()
    return {"status": "setup_started", "message": (
        "Enter your ILIAS details in the browser window. If you changed a previously used account or password, "
        "restart Claude Desktop after saving. The extension log has the local setup address if no browser opens."
    )}


if __name__ == "__main__":
    server.mcp.add_tool(
        ilias_setup,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    server.main(require_account=False)
