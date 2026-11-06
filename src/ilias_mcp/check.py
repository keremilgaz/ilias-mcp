"""`ilias-mcp-check`: log in once and test the parsers against the real ILIAS.

Writes a JSON report (no passwords, no cookies). With --dump, also saves the
fetched HTML pages, with rtoken values and hidden form values blanked, so the
parsers can be adjusted to the real markup.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import traceback
from pathlib import Path

from . import __version__, parsers
from .client import IliasClient
from .config import load_settings
from .files import FileCache
from .service import IliasService


def _redact(html: str) -> str:
    html = re.sub(r"(rtoken=)[A-Za-z0-9_-]+", r"\1REDACTED", html)
    html = re.sub(r'(<input[^>]*type="hidden"[^>]*value=")[^"]*', r"\1REDACTED", html, flags=re.I)
    return html


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="selftest-report.json")
    ap.add_argument("--dump", metavar="DIR", help="save redacted HTML of the pages fetched")
    ap.add_argument("--courses", type=int, default=2, help="how many courses to open (default 2)")
    args = ap.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = load_settings()
    client = IliasClient(settings)
    service = IliasService(settings, client, FileCache(Path(settings.cache_dir) / "files"))
    report: dict = {"version": __version__, "base_url": settings.base_url, "steps": []}
    dump = Path(args.dump) if args.dump else None
    if dump:
        dump.mkdir(parents=True, exist_ok=True)

    original_get = client.get_page
    counter = {"n": 0}

    def recording_get(url: str):
        page = original_get(url)
        counter["n"] += 1
        if dump:
            name = f"{counter['n']:02d}.html"
            (dump / name).write_text(_redact(page.html), "utf-8")
            with open(dump / "index.txt", "a", encoding="utf-8") as fh:
                fh.write(f"{name}\t{re.sub(r'rtoken=[^&]+', 'rtoken=REDACTED', page.url)}\n")
        return page

    client.get_page = recording_get  # type: ignore[method-assign]

    def step(name: str, fn):
        entry: dict = {"step": name}
        try:
            with client.call_scope(80):
                entry["result"] = fn()
            entry["ok"] = "error" not in entry["result"]
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["trace"] = traceback.format_exc(limit=4)
        report["steps"].append(entry)
        print(("OK   " if entry["ok"] else "FAIL ") + name, file=sys.stderr)
        return entry

    courses = step("list_courses", service.list_courses)
    picked = []
    if courses.get("ok"):
        picked = [c for c in courses["result"]["courses"] if c.get("ref_id")][: args.courses]
    for course in picked:
        ref = f"{course['type']}/{course['ref_id']}"
        crawl = step(f"list_items {ref}", lambda r=ref: service.crawl(r, depth=1))
        items = crawl.get("result", {}).get("items", []) if crawl.get("ok") else []
        exc = next((i for i in items if i["type"] == "exc" and i.get("ref_id")), None)
        frm = next((i for i in items if i["type"] == "frm" and i.get("ref_id")), None)
        if exc:
            step(f"assignments exc/{exc['ref_id']}", lambda e=exc: service.assignments(f"exc/{e['ref_id']}"))
        if frm:
            step(f"forum frm/{frm['ref_id']}", lambda f=frm: service.forum_topics(f"frm/{f['ref_id']}"))
    step("news", service.news)

    report["requests"] = client.requests_total
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print(f"report: {Path(args.report).resolve()}  ({client.requests_total} requests)", file=sys.stderr)
    client.close()
    sys.exit(0 if all(s.get("ok") for s in report["steps"]) else 1)


if __name__ == "__main__":
    main()
