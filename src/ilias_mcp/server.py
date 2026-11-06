"""MCP server (stdio). Nothing here writes to ILIAS; policy.py enforces that."""

from __future__ import annotations

import functools
import importlib
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

import anyio
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import __version__, dates, parsers
from .client import BudgetExceeded, IliasClient, IliasError, LoginError
from .config import Settings, load_settings
from .credentials import CredentialError
from .files import FileCache
from .policy import PolicyViolation
from .service import IliasService

log = logging.getLogger("ilias_mcp")

INSTRUCTIONS = """\
Read-only access to the user's own ILIAS courses (University of Konstanz).
Nothing here can submit, post, join, leave, delete or mark anything as read:
the client only sends GET requests and refuses state-changing links.

Typical flow: ilias_check_all (every course of the current semester in one
call; returns only what changed since the last committed check) ->
ilias_read_file for new PDFs -> ilias_commit_scan(check_id) once the findings
are recorded. ilias_scan does the same for a single course.
ilias_read_file remembers which pages of which file version were read and
returns 'already_read' for unchanged files unless pages are asked for.
Targets accept a URL, 'crs/123' style references or a bare ref_id.
Requests are rate-limited (one per second), so a full check takes about a
minute; ilias_check_all keeps working in the background and is simply called
again until it returns its result.
"""

mcp = MCPServer(name="ilias", version=__version__, instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)

_service: IliasService | None = None
_settings: Settings | None = None
_mtimes: dict[str, float] = {}


def configure(service: IliasService) -> None:
    """Inject a service (tests)."""
    global _service
    _service = service


def get_service() -> IliasService:
    global _service, _settings
    if _service is None:
        _settings = load_settings()
        client = IliasClient(_settings)
        _service = IliasService(_settings, client, FileCache(Path(_settings.cache_dir) / "files"))
    return _service


def _reload_parsers() -> None:
    """Pick up edits to the HTML parsers without restarting the app."""
    changed = False
    for module in (dates, parsers):
        mtime = Path(module.__file__).stat().st_mtime
        if changed or _mtimes.setdefault(module.__name__, mtime) != mtime:
            importlib.reload(module)
            _mtimes[module.__name__] = Path(module.__file__).stat().st_mtime
            changed = True
            log.info("reloaded %s", module.__name__)


def _tool(limit: int | None = None) -> Callable:
    """Run the body in a worker thread, inside one request budget, with errors as data."""

    def decorate(fn: Callable[..., dict]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> dict:
            def work() -> dict:
                service = get_service()
                _reload_parsers()
                try:
                    with service.client.call_scope(limit):
                        return fn(service, *args, **kwargs)
                except PolicyViolation as exc:
                    return {"error": f"blocked by the read-only policy: {exc}"}
                except (LoginError, CredentialError) as exc:
                    return {"error": f"login problem: {exc}"}
                except BudgetExceeded as exc:
                    return {"error": str(exc)}
                except IliasError as exc:
                    return {"error": str(exc)}
                except httpx.HTTPError as exc:
                    return {"error": f"network error: {type(exc).__name__}: {exc}"}
                except ValueError as exc:
                    return {"error": str(exc)}

            return await anyio.to_thread.run_sync(work)

        # MCP builds the schema from the visible signature, minus `service`.
        import inspect

        sig = inspect.signature(fn)
        wrapper.__signature__ = sig.replace(parameters=list(sig.parameters.values())[1:])  # type: ignore[attr-defined]
        del wrapper.__wrapped__  # type: ignore[attr-defined]
        return wrapper

    return decorate


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_status(service: IliasService) -> dict:
    """Configuration, login state, request counter and the read-only policy. No network."""
    return service.status()


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_list_courses(service: IliasService) -> dict:
    """The user's courses and groups from the ILIAS dashboard, with ref_ids and semester sections."""
    return service.list_courses()


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_list_items(service: IliasService, target: str, depth: int = 0) -> dict:
    """Objects in a course/folder/group/session: type, title, ref_id, file version/date/size.

    depth > 0 also lists sub-folders, groups and sessions (max 3). Files carry
    'already_read' when this version was read before.
    """
    return service.crawl(target, depth=max(0, min(int(depth), 3)))


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_page_text(
    service: IliasService, target: str, offset: int = 0, max_chars: int = 12000, include_links: bool = False
) -> dict:
    """Readable text of any ILIAS page (course page notes, info screens, a news item).

    Use when a structured tool misses something. Paginate with offset/next_offset.
    """
    return service.page_text(target, offset=max(0, offset), max_chars=max(500, min(max_chars, 40000)),
                             include_links=include_links)


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_list_assignments(service: IliasService, target: str) -> dict:
    """Assignments of an exercise object ('Show all' view): deadlines, start, submission status, files."""
    return service.assignments(target)


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_read_file(
    service: IliasService,
    target: str,
    pages: str | None = None,
    query: str | None = None,
    force: bool = False,
    max_chars: int = 15000,
) -> dict:
    """Text of a course file (PDF, PPTX, DOCX, text, ZIP) by ref_id or download URL.

    Without `pages`, returns only pages not read before; an unchanged, fully read
    file returns status 'already_read'. `pages='2-4,7'` re-opens specific pages.
    `query='deadline|due|submit'` returns keyword snippets instead of full text
    (not counted as read). `force=true` returns everything again.
    """
    return service.read_file(target, pages=pages, query=query, force=force,
                             max_chars=max(1000, min(max_chars, 60000)))


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_list_forum_topics(service: IliasService, target: str) -> dict:
    """Thread list of a forum (titles, authors, counts, last activity). Threads are never opened."""
    return service.forum_topics(target)


@mcp.tool(annotations=READ_ONLY)
@_tool()
def ilias_list_news(service: IliasService, target: str | None = None) -> dict:
    """News items from the dashboard news page, or from a given course page."""
    return service.news(target)


@mcp.tool(annotations=READ_ONLY)
@_tool(limit=120)
def ilias_scan(
    service: IliasService,
    target: str,
    depth: int = 1,
    include_assignments: bool = True,
    include_forums: bool = True,
) -> dict:
    """Crawl one course and report new / changed / removed items, assignments and forum threads
    compared with the last committed scan. Returns a scan_id; call ilias_commit_scan after the
    findings have been recorded so the next scan compares against this one.
    """
    return service.scan(target, depth=max(0, min(int(depth), 3)),
                        include_assignments=include_assignments, include_forums=include_forums)


# -- ilias_check_all: one call for the whole semester ------------------------------
# A full check takes longer than clients like to wait for one tool call, so it
# runs in a background thread. Each call waits up to `wait_seconds` and returns
# either the result or a progress report; calling again keeps waiting on the
# same check instead of starting a new one.

_job_lock = threading.Lock()
_job: dict[str, Any] | None = None


def _start_check(service: IliasService, exclude: list[str], section: str | None, depth: int) -> dict:
    job: dict[str, Any] = {"done": threading.Event(), "result": None, "progress": {},
                           "started": time.monotonic(), "collected": False}

    def run() -> None:
        try:
            with service.client.call_scope(400):
                job["result"] = service.check_all(exclude=exclude, section=section, depth=depth,
                                                  progress=job["progress"].update)
        except PolicyViolation as exc:
            job["result"] = {"error": f"blocked by the read-only policy: {exc}"}
        except (LoginError, CredentialError) as exc:
            job["result"] = {"error": f"login problem: {exc}"}
        except Exception as exc:  # report anything else instead of losing the job
            job["result"] = {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            job["done"].set()

    threading.Thread(target=run, name="ilias-check-all", daemon=True).start()
    return job


@mcp.tool(annotations=READ_ONLY)
async def ilias_check_all(
    exclude: list[str] | None = None,
    section: str | None = None,
    depth: int = 1,
    wait_seconds: int = 40,
) -> dict:
    """Check every course of the current semester in one go and return only what changed
    since the last committed check: new/changed/removed files, assignments, forum threads
    and course-page text, plus deadlines in the next 14 days and new dashboard news.

    The semester is the newest dashboard section unless `section` is given; `exclude`
    takes ref_ids ('2101331' or 'crs/2101331') of courses to skip. The check runs in the
    background: if the answer is status 'running', call this tool again to keep waiting
    (it does not start a second check). Afterwards call ilias_commit_scan(check_id).
    """

    def work() -> dict:
        global _job
        service = get_service()
        with _job_lock:
            job = _job
            if job is None or job["collected"]:
                _reload_parsers()
                job = _job = _start_check(service, list(exclude or []), section, max(0, min(int(depth), 3)))
        if job["done"].wait(timeout=max(1, min(int(wait_seconds), 55))):
            with _job_lock:
                job["collected"] = True
            return job["result"]
        return {
            "status": "running",
            "progress": dict(job["progress"]),
            "elapsed_seconds": round(time.monotonic() - job["started"]),
            "hint": "Still checking (one request per second). Call ilias_check_all again to keep waiting.",
        }

    return await anyio.to_thread.run_sync(work)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
@_tool()
def ilias_commit_scan(service: IliasService, scan_id: str) -> dict:
    """Make a scan, or a whole ilias_check_all check (pass its check_id), the new baseline.
    Local bookkeeping only; nothing is sent to ILIAS."""
    return service.commit_scan(scan_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
@_tool()
def ilias_download_file(service: IliasService, target: str, dest_dir: str) -> dict:
    """Save a course file to a folder inside the configured download root
    (ILIAS_DOWNLOAD_ROOT, default ~/Documents/ILIAS). Never overwrites a different file.
    """
    return service.download_file(target, dest_dir)


def main() -> None:
    logging.basicConfig(
        stream=sys.stderr,  # stdout carries the MCP protocol
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    get_service()  # fail fast on missing ILIAS_USER
    mcp.run("stdio")


if __name__ == "__main__":
    main()
