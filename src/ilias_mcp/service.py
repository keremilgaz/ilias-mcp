"""The operations behind the MCP tools. Synchronous and network-agnostic:
everything goes through :class:`IliasClient`, so tests can swap the transport.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import dates, parsers
from .client import BudgetExceeded, IliasClient, IliasError, LoginError, Page
from .config import Settings
from .policy import PolicyViolation
from .files import (
    FileCache,
    compact_ranges,
    listing_signature,
    parse_page_spec,
    search_pages,
)

CRAWLABLE = {"fold", "grp", "sess", "copa"}
_TYPED_TARGET = re.compile(r"([a-z]{2,5})[/_](\d+)")
_SEMESTER = re.compile(
    r"(?P<season>winter|wintersemester|wise|ws|summer|sommersemester|sose|ss)\D{0,12}(?P<year>\d{4})", re.I
)


def latest_semester(sections: Iterable[str]) -> str | None:
    """The newest semester label among dashboard sections ('Wintersemester 2026' > 'Sommersemester 2026')."""
    best: tuple[tuple[int, int], str] | None = None
    for section in set(sections):
        match = _SEMESTER.search(section or "")
        if not match:
            continue
        winter = match.group("season").lower().startswith("w")
        key = (int(match.group("year")), 1 if winter else 0)
        if best is None or key > best[0]:
            best = (key, section)
    return best[1] if best else None


def target_url(target: str) -> str:
    """Accept a URL, an ILIAS path, 'crs/123', 'crs_123' or a bare ref_id."""
    target = str(target).strip()
    if target.startswith(("https://", "http://")):
        return target
    if target.startswith("/"):
        return target
    match = re.fullmatch(r"([a-z]{2,5})[/_](\d+)", target)
    if match:
        return f"/goto.php/{match.group(1)}/{match.group(2)}"
    if target.isdigit():
        return f"/ilias.php?baseClass=ilrepositorygui&ref_id={target}"
    raise ValueError(f"cannot interpret target {target!r}; use a URL, 'crs/123' or a ref_id")


def _ref_of(target: str) -> str | None:
    target = str(target).strip()
    if target.isdigit():
        return target
    match = re.fullmatch(r"[a-z]{2,5}[/_](\d+)", target)
    if match:
        return match.group(1)
    return parsers.ref_from_url(target)[1]


class IliasService:
    def __init__(self, settings: Settings, client: IliasClient, cache: FileCache) -> None:
        self.settings = settings
        self.client = client
        self.cache = cache
        self.snapshots = settings.account_dir / "snapshots"
        (self.snapshots / "pending").mkdir(parents=True, exist_ok=True)
        # File listings seen in this process; trusted to skip a re-download.
        self._fresh_listing: dict[str, dict] = {}
        # Direct ilias.php routes per object type, learned from goto redirects.
        # Using them skips the redirect hop: one request per page instead of two.
        self._routes_path = settings.account_dir / "routes.json"
        self._routes: dict[str, dict] = self._load_routes()

    # -- routes ------------------------------------------------------------------

    def _load_routes(self) -> dict[str, dict]:
        try:
            return json.loads(self._routes_path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_routes(self) -> None:
        self._routes_path.parent.mkdir(parents=True, exist_ok=True)
        self._routes_path.write_text(json.dumps(self._routes, indent=1), "utf-8")

    def _route_url(self, kind: str, ref: str, extra: dict[str, str] | None = None) -> str | None:
        route = self._routes.get(kind)
        if not route:
            return None
        params = [(k, ref if v == "{ref}" else v) for k, v in route["params"] if k not in (extra or {})]
        params.extend((extra or {}).items())
        return route["path"] + "?" + urlencode(params)

    def _learn_route(self, kind: str, ref: str, final_url: str) -> None:
        parts = urlsplit(final_url)
        params = parse_qsl(parts.query, keep_blank_values=True)
        lowered = {(k.lower(), v) for k, v in params}
        if not parts.path.endswith("/ilias.php") or ("ref_id", ref) not in lowered:
            return
        if not any(k == "cmdclass" for k, _ in lowered):
            return  # without the GUI class the route is not specific enough
        route = {
            "path": parts.path,
            "params": [(k, "{ref}" if k.lower() == "ref_id" else v) for k, v in params
                       if k.lower() not in ("rtoken", "mode", "from_overview")],
        }
        if self._routes.get(kind) != route:
            self._routes[kind] = route
            self._save_routes()

    def _get_object(self, kind: str, ref: str, fallback_url: str | None = None,
                    extra: dict[str, str] | None = None) -> Page:
        """Open an object by type and ref_id: learned direct route first, goto link otherwise."""
        url = self._route_url(kind, ref, extra)
        if url:
            try:
                page = self.client.get_page(url)
                if parsers.query_param(page.url, "ref_id") == ref:
                    return page
            except (LoginError, BudgetExceeded):
                raise
            except (IliasError, PolicyViolation):
                pass
            self._routes.pop(kind, None)  # the route no longer works; relearn it
            self._save_routes()
        page = self.client.get_page(fallback_url or f"/goto.php/{kind}/{ref}")
        self._learn_route(kind, ref, page.url)
        return page

    def _open(self, target: str) -> Page:
        match = _TYPED_TARGET.fullmatch(str(target).strip())
        if match:
            return self._get_object(match.group(1), match.group(2))
        return self.client.get_page(target_url(target))

    # -- status ----------------------------------------------------------------

    def status(self) -> dict:
        return {
            "base_url": self.settings.base_url,
            "user": self.settings.username,
            "logged_in": self.client.logged_in,
            "requests_this_process": self.client.requests_total,
            "min_seconds_between_requests": self.settings.min_interval,
            "max_requests_per_call": self.settings.max_requests_per_call,
            "cache_dir": str(self.settings.account_dir),
            "download_root": str(self.settings.download_root),
            "policy": self.client.policy.describe(),
        }

    # -- courses -----------------------------------------------------------------

    def list_courses(self) -> dict:
        page = self.client.get_page(self.settings.dashboard_url)
        courses = [i for i in parsers.parse_items(page.html, page.url) if i["type"] in ("crs", "grp")]
        source = "dashboard"
        if not courses:
            page = self.client.get_page(self.settings.memberships_url)
            courses = [i for i in parsers.parse_items(page.html, page.url) if i["type"] in ("crs", "grp")]
            source = "memberships"
        result: dict[str, Any] = {"source": source, "courses": courses}
        if not courses:
            result["hint"] = "no courses recognised; page text follows"
            result["text"] = parsers.page_text(page.html)[:4000]
        return result

    # -- containers --------------------------------------------------------------

    def _annotate(self, item: dict) -> dict:
        if item.get("type") == "file" and item.get("ref_id"):
            listing = listing_signature(item)
            self._fresh_listing[item["ref_id"]] = listing
            self.cache.remember_listing(item["ref_id"], item["title"], listing)
            state = self.cache.status(item["ref_id"], listing)
            if state:
                item["already_read"] = state
        return item

    def crawl(self, target: str, depth: int = 0) -> dict:
        root = self._open(target)
        root_ref = parsers.ref_from_url(root.url)[1] or _ref_of(target)
        root_text = parsers.page_text(root.html)
        result: dict[str, Any] = {
            "page": {
                "title": parsers.page_title(root.html),
                "url": root.url,
                "ref_id": root_ref,
                # Lets a scan notice edited announcements / schedules on the page itself.
                "text_sha": hashlib.sha256(root_text.encode()).hexdigest()[:16],
                "text_excerpt": root_text[:300],
            },
            "items": [],
        }
        queue: list[tuple[str, list[str], int, str]] = [(root.url, [], 0, root.html)]
        visited = {root_ref or root.url}
        while queue:
            url, path, level, html = queue.pop(0)
            for item in parsers.parse_items(html, url):
                if item.get("ref_id") and item["ref_id"] == root_ref:
                    continue
                if path:
                    item["path"] = " / ".join(path)
                result["items"].append(self._annotate(item))
                key = item.get("ref_id") or item["url"]
                if level < depth and item["type"] in CRAWLABLE and key not in visited:
                    visited.add(key)
                    if self.client.budget_left() < 3:
                        result["truncated"] = "request budget reached; crawl sub-folders separately"
                        continue
                    try:
                        child = (
                            self._get_object(item["type"], item["ref_id"], item["url"])
                            if item.get("ref_id") else self.client.get_page(item["url"])
                        )
                    except (LoginError, BudgetExceeded):
                        raise
                    except (IliasError, PolicyViolation) as exc:  # skip this branch, keep crawling
                        result.setdefault("errors", []).append(f"{item['title']}: {exc}")
                        continue
                    queue.append((child.url, path + [item["title"]], level + 1, child.html))
        if not result["items"]:
            result["hint"] = "no listed objects recognised; page text follows"
            result["text"] = parsers.page_text(root.html)[:4000]
        result["requests_used"] = self.client.call_requests
        return result

    def page_text(self, target: str, offset: int = 0, max_chars: int = 12000, include_links: bool = False) -> dict:
        page = self._open(target)
        text = parsers.page_text(page.html)
        chunk = text[offset : offset + max_chars]
        result: dict[str, Any] = {
            "title": parsers.page_title(page.html),
            "url": page.url,
            "text": chunk,
            "total_chars": len(text),
        }
        if offset + max_chars < len(text):
            result["next_offset"] = offset + max_chars
        if include_links:
            result["links"] = parsers.page_links(page.html, page.url)
        return result

    # -- exercises ---------------------------------------------------------------

    def _show_all_url(self, page_url: str, html: str) -> str:
        found = parsers.find_show_all_url(html, page_url)
        if found:
            return found
        parts = urlsplit(page_url)
        query = dict(parse_qsl(parts.query))
        query.update({"cmd": "showOverview", "mode": "all", "from_overview": "1"})
        query.pop("rtoken", None)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    def assignments(self, target: str) -> dict:
        match = _TYPED_TARGET.fullmatch(str(target).strip())
        show_all = {"cmd": "showOverview", "mode": "all", "from_overview": "1"}
        if match and match.group(1) == "exc" and "exc" in self._routes:
            page = self._get_object("exc", match.group(2), extra=show_all)  # one request
        else:
            page = self._open(target)
        if "mode=all" not in page.url.lower():
            page = self.client.get_page(self._show_all_url(page.url, page.html))
        found = parsers.parse_assignments(page.html, page.url)
        now = dates.now_berlin()
        for entry in found:
            if entry.get("deadline"):
                entry["deadline_passed"] = dates.parse_iso(entry["deadline"]) < now
        result: dict[str, Any] = {
            "exercise": parsers.page_title(page.html),
            "url": page.url,
            "assignments": found,
        }
        if not found:
            result["hint"] = "no assignments recognised; page text follows"
            result["text"] = parsers.page_text(page.html)[:12000]
        return result

    # -- forums and news ---------------------------------------------------------

    def forum_topics(self, target: str) -> dict:
        page = self._open(target)
        threads = parsers.parse_forum_threads(page.html, page.url)
        result: dict[str, Any] = {"forum": parsers.page_title(page.html), "url": page.url, "threads": threads}
        if not threads:
            result["hint"] = "no threads recognised (or the forum is empty); page text follows"
            result["text"] = parsers.page_text(page.html)[:6000]
        return result

    def news(self, target: str | None = None) -> dict:
        page = self._open(target) if target else self._news_page(self.client.get_page(self.settings.dashboard_url))
        items = parsers.parse_news(page.html, page.url)
        result: dict[str, Any] = {"source": parsers.page_title(page.html), "url": page.url, "news": items}
        if not items:
            result["hint"] = "no news items recognised; page text follows"
            result["text"] = parsers.page_text(page.html)[:6000]
        return result

    def _news_page(self, dash: Page) -> Page:
        """The dashboard's news page; the dashboard itself shows only a few items, if any."""
        link = parsers.find_link(dash.html, dash.url, r"ilpdnewsgui")
        return self.client.get_page(link) if link else dash

    # -- files -------------------------------------------------------------------

    def _file_key_and_urls(self, target: str) -> tuple[str, list[str]]:
        target = str(target).strip()
        ref = _ref_of(target)
        is_url = target.startswith(("http://", "https://", "/"))
        if ref and (not is_url or "sendfile" in target or "/file/" in target):
            return ref, [
                self.settings.sendfile_template.format(ref_id=ref),
                f"/goto.php/file/{ref}/download",
            ]
        if is_url:
            return "url:" + hashlib.sha1(target.encode()).hexdigest()[:16], [target]
        raise ValueError(f"cannot interpret file target {target!r}")

    def read_file(
        self,
        target: str,
        pages: str | None = None,
        query: str | None = None,
        force: bool = False,
        max_chars: int = 15000,
        offset: int = 0,
    ) -> dict:
        key, urls = self._file_key_and_urls(target)
        listing = self._fresh_listing.get(key)
        entry = None
        source = "cache"
        if listing and not force:
            entry = self.cache.version(key, listing=listing)
        if entry is None:
            download = self.client.get_file(urls)
            versions_before = self.cache.version_count(key)
            entry = self.cache.store(key, download.content, download.filename, listing)
            source = "downloaded"
            if versions_before and self.cache.version_count(key) > versions_before:
                source = "downloaded_new_version"  # content differs from what was seen before
        texts = self.cache.pages(entry["sha256"])
        total = len(texts)
        result: dict[str, Any] = {
            "ref_id": key,
            "filename": entry.get("filename"),
            "kind": entry["kind"],
            "pages_total": total,
            "source": source,
        }
        if listing:
            result["listing"] = listing
        if entry["read_pages"]:
            result["previously_read"] = compact_ranges(entry["read_pages"])
            result["last_read"] = entry.get("last_read")
        if not total:
            result["note"] = "no extractable text (scanned PDF or unsupported format)"
            return result

        if query:
            selected = parse_page_spec(pages, total)
            hits = search_pages({p: texts[p - 1] for p in selected}, query)
            budget, kept = max_chars, []
            for hit in hits:
                if budget - len(hit["snippet"]) < 0:
                    result["hits_truncated"] = len(hits) - len(kept)
                    break
                kept.append(hit)
                budget -= len(hit["snippet"])
            result["query"] = query
            result["hits"] = kept
            result["pages_with_hits"] = compact_ranges([h["page"] for h in hits])
            return result

        if pages:
            selected = parse_page_spec(pages, total)
        else:
            unread = [p for p in range(1, total + 1) if p not in set(entry["read_pages"])]
            if not unread and not force:
                result["status"] = "already_read"
                result["hint"] = (
                    "This exact version was fully read before. Use pages='3-4' to re-open "
                    "specific pages, query='deadline|due' to search, or force=true."
                )
                return result
            selected = unread if not force else list(range(1, total + 1))

        # `offset` continues a page that was cut off (one long page: a text file, a
        # ZIP listing, a dense slide). It applies to the first selected page.
        if offset and selected and (offset < 0 or offset >= len(texts[selected[0] - 1])):
            raise ValueError(f"offset {offset} is outside page {selected[0]} "
                             f"({len(texts[selected[0] - 1])} characters)")
        returned: list[dict] = []
        budget = max_chars
        cut: dict | None = None
        for number in selected:
            text = texts[number - 1]
            start = offset if not returned else 0
            if returned and len(text) - start > budget:
                break
            chunk = text[start:start + budget]
            returned.append({"page": number, "text": chunk} | ({"offset": start} if start else {}))
            budget -= len(chunk)
            if start + len(chunk) < len(text):
                cut = {"page": number, "next_offset": start + len(chunk), "page_chars": len(text)}
                break
        # A page counts as read once its end has been returned.
        done = [r["page"] for r in returned
                if r.get("offset", 0) + len(r["text"]) == len(texts[r["page"] - 1])]
        self.cache.mark_read(key, entry["sha256"], done)
        remaining = [p for p in selected if p not in done]
        result["returned_pages"] = compact_ranges([r["page"] for r in returned])
        if remaining:
            result["remaining_pages"] = compact_ranges(remaining)
        if cut:
            result["continue_with"] = {"pages": str(cut["page"]), "offset": cut["next_offset"]}
            result["hint"] = (f"page {cut['page']} was cut at character {cut['next_offset']} of "
                              f"{cut['page_chars']}; call again with continue_with's pages and offset")
        result["text"] = returned
        return result

    def download_file(self, target: str, dest_dir: str) -> dict:
        root = Path(self.settings.download_root).expanduser().resolve()
        dest = Path(dest_dir).expanduser()
        dest = (dest if dest.is_absolute() else root / dest).resolve()
        if dest != root and root not in dest.parents:
            raise ValueError(f"dest_dir must be inside {root}")
        key, urls = self._file_key_and_urls(target)
        download = self.client.get_file(urls)
        self.cache.store(key, download.content, download.filename, self._fresh_listing.get(key))
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", download.filename or f"ilias-{key}.bin").strip().rstrip(".") or "file"
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / name
        digest = hashlib.sha256(download.content).hexdigest()
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                return {"saved_to": str(path), "status": "already_present"}
            stem, suffix, n = path.stem, path.suffix, 2
            while path.exists():
                path = dest / f"{stem} ({n}){suffix}"
                n += 1
        path.write_bytes(download.content)
        return {"saved_to": str(path), "bytes": len(download.content), "status": "saved"}

    # -- change detection ----------------------------------------------------------

    def scan(self, target: str, depth: int = 1, include_assignments: bool = True,
             include_forums: bool = True) -> dict:
        crawl = self.crawl(target, depth=depth)
        course_ref = crawl["page"]["ref_id"] or _ref_of(target) or "unknown"
        state: dict[str, dict] = {
            f"page:{course_ref}": {
                "title": crawl["page"]["title"],
                "text_sha": crawl["page"]["text_sha"],
                "_excerpt": crawl["page"]["text_excerpt"],
            }
        }
        notes: list[str] = []
        for item in crawl["items"]:
            sig = {k: item.get(k) for k in ("type", "title", "version", "date", "size") if item.get(k)}
            if item["type"] != "file" and item.get("description"):
                sig["description"] = item["description"][:200]
            if item.get("path"):
                sig["path"] = item["path"]
            if item.get("already_read"):
                sig["_already_read"] = item["already_read"]
            state[f"item:{item.get('ref_id') or item['url']}"] = sig
        for item in crawl["items"]:
            ref = item.get("ref_id")
            if not ref or self.client.budget_left() < 4:
                if ref and item["type"] in ("exc", "frm"):
                    notes.append(f"skipped {item['type']} {ref}: request budget")
                continue
            try:
                if include_assignments and item["type"] == "exc":
                    for a in self.assignments(f"exc/{ref}")["assignments"]:
                        state[f"ass:{ref}:{a['ass_id']}"] = {
                            k: a.get(k) for k in ("title", "deadline", "start", "submitted", "last_submission")
                            if a.get(k) is not None
                        } | {"exercise": item["title"]}
                elif include_forums and item["type"] == "frm":
                    for t in self.forum_topics(f"frm/{ref}")["threads"]:
                        # Total posts and last activity only: unread counts change when
                        # the user reads a thread in the browser, which is not news.
                        state[f"thr:{ref}:{t['thread_id']}"] = {
                            k: v for k, v in (("forum", item["title"]), ("title", t["title"]),
                                              ("last_activity", t.get("last_activity")),
                                              ("posts", t.get("posts")))
                            if v is not None
                        }
            except Exception as exc:  # keep scanning the rest
                notes.append(f"{item['type']} {ref}: {type(exc).__name__}: {exc}")

        previous_path = self.snapshots / f"{course_ref}.json"
        previous = json.loads(previous_path.read_text("utf-8")) if previous_path.exists() else None
        before = (previous or {}).get("state", {})
        strip = lambda s: {k: v for k, v in s.items() if not k.startswith("_")}  # noqa: E731
        new = {k: v for k, v in state.items() if k not in before}
        if previous is not None and not any(k.startswith("page:") for k in before):
            new.pop(f"page:{course_ref}", None)  # baseline predates page tracking: adopt, don't report
        changed = {
            k: {"before": strip(before[k]), "after": strip(v)}
            for k, v in state.items()
            if k in before and strip(before[k]) != strip(v)
        }
        if crawl.get("truncated"):
            notes.append(crawl["truncated"])
        notes.extend(f"could not open {e}" for e in crawl.get("errors", []))
        missing = {k: strip(v) for k, v in before.items() if k not in state}
        # An incomplete scan cannot tell a deleted item from one it could not reach.
        # Unseen items stay in the baseline (so they do not come back as "new" once
        # the folder opens again) and are reported as not seen instead of removed.
        incomplete = bool(notes)
        removed = {} if incomplete else missing
        not_seen = missing if incomplete else {}
        saved_state = {**{k: before[k] for k in not_seen}, **state}
        scan_id = uuid.uuid4().hex[:12]
        pending = {"target": course_ref, "title": crawl["page"]["title"], "state": saved_state,
                   "scanned_at": dates.now_berlin().isoformat(timespec="minutes")}
        if incomplete:
            pending["kept_unseen"] = len(not_seen)
        (self.snapshots / "pending" / f"{scan_id}.json").write_text(
            json.dumps(pending, ensure_ascii=False), "utf-8"
        )
        result: dict[str, Any] = {
            "scan_id": scan_id,
            "course": crawl["page"]["title"],
            "ref_id": course_ref,
            "compared_with": previous.get("committed_at") if previous else None,
            "new": [{"key": k, **strip(v)} for k, v in new.items()],
            "changed": [{"key": k, **v} for k, v in changed.items()],
            "removed": [{"key": k, **v} for k, v in removed.items()],
            "unchanged_count": len(state) - len(new) - len(changed),
            "upcoming_deadlines": sorted(
                ({"key": k, **v} for k, v in state.items()
                 if k.startswith("ass:") and v.get("deadline")
                 and dates.parse_iso(v["deadline"]) >= dates.now_berlin()),
                key=lambda a: a["deadline"],
            ),
            "requests_used": self.client.call_requests,
        }
        if previous is None:
            result["note"] = "first scan of this course: everything is listed as new"
        if incomplete:
            result["notes"] = notes
            result["incomplete"] = True
            result["not_seen"] = [{"key": k, **v} for k, v in not_seen.items()]
            result["warning"] = (
                f"incomplete scan (see 'notes'): {len(not_seen)} item(s) of the last baseline were "
                "not reached. They are listed under 'not_seen', not as removed, and committing keeps "
                "them in the baseline until a complete scan confirms whether they still exist."
            )
        return result

    def commit_scan(self, scan_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{12}", scan_id or ""):
            raise ValueError("invalid scan_id")
        bundle_path = self.snapshots / "pending" / f"check-{scan_id}.json"
        if bundle_path.exists():
            return self._commit_check(scan_id, bundle_path)
        pending_path = self.snapshots / "pending" / f"{scan_id}.json"
        if not pending_path.exists():
            raise ValueError("unknown or already committed scan_id")
        pending = json.loads(pending_path.read_text("utf-8"))
        pending["committed_at"] = dates.now_berlin().isoformat(timespec="minutes")
        target = self.snapshots / f"{pending['target']}.json"
        target.write_text(json.dumps(pending, ensure_ascii=False), "utf-8")
        pending_path.unlink()
        result = {"committed": scan_id, "course": pending.get("title"), "baseline_from": pending["scanned_at"]}
        if pending.get("kept_unseen"):
            result["kept_unseen"] = pending["kept_unseen"]  # carried over from the previous baseline
        return result

    # -- one call for the whole semester -------------------------------------------

    def check_all(
        self,
        exclude: Iterable[str] = (),
        section: str | None = None,
        depth: int = 1,
        progress: Callable[[dict], None] | None = None,
        auto_commit: bool = True,
    ) -> dict:
        """Scan every course of the current semester and return only what changed.

        With ``auto_commit`` a check that found nothing new commits itself.
        """
        dash = self.client.get_page(self.settings.dashboard_url)
        entries = [i for i in parsers.parse_items(dash.html, dash.url)
                   if i["type"] in ("crs", "grp") and i.get("ref_id")]
        chosen = section or latest_semester(i.get("section", "") for i in entries)
        excluded = {str(x).strip().split("/")[-1].split("_")[-1] for x in exclude}
        targets = [i for i in entries
                   if (chosen is None or i.get("section") == chosen) and i["ref_id"] not in excluded]
        news_notes: list[str] = []
        try:
            news_page = self._news_page(dash)  # same source as ilias_list_news
        except (LoginError, BudgetExceeded):
            raise
        except (IliasError, PolicyViolation) as exc:
            news_page = dash
            news_notes.append(f"news page could not be opened ({exc}); only dashboard news checked")
        news = parsers.parse_news(news_page.html, news_page.url)
        last_check = self._last_check()

        courses: list[dict] = []
        deadlines: list[dict] = []
        scan_ids: list[str] = []
        for number, course in enumerate(targets, 1):
            if progress:
                progress({"course": course["title"], "course_number": number, "courses": len(targets),
                          "requests": self.client.call_requests})
            try:
                scan = self.scan(f"{course['type']}/{course['ref_id']}", depth=depth)
            except (LoginError, BudgetExceeded):
                raise
            except Exception as exc:  # one broken course must not hide the others
                courses.append({"course": course["title"], "ref_id": course["ref_id"],
                                "error": f"{type(exc).__name__}: {exc}"})
                continue
            scan_ids.append(scan["scan_id"])
            entry = {"course": scan["course"], "ref_id": scan["ref_id"],
                     "changes": len(scan["new"]) + len(scan["changed"]) + len(scan["removed"])}
            for key in ("new", "changed", "removed", "not_seen", "notes", "incomplete", "warning", "note",
                        "compared_with"):
                if scan.get(key):
                    entry[key] = scan[key]
            courses.append(entry)
            deadlines.extend({"course": scan["course"], **d} for d in scan["upcoming_deadlines"])

        now = dates.now_berlin()
        horizon = now + timedelta(days=14)
        upcoming = sorted((d for d in deadlines if dates.parse_iso(d["deadline"]) <= horizon),
                          key=lambda d: d["deadline"])
        fresh_news = [n for n in news if last_check is None
                      or (n.get("date") and dates.parse_iso(n["date"]) > dates.parse_iso(last_check))]
        check_id = uuid.uuid4().hex[:12]
        (self.snapshots / "pending" / f"check-{check_id}.json").write_text(json.dumps(
            {"scan_ids": scan_ids, "checked_at": now.isoformat(timespec="minutes")}), "utf-8")

        attention = [c for c in courses if c.get("changes") or c.get("error") or c.get("incomplete")]
        quiet = [c["course"] for c in courses if c not in attention]
        # Nothing to record: make this the baseline right away, so a quiet check
        # needs no further tool call (and no further approval) from the client.
        nothing_new = not attention and not fresh_news and not news_notes and bool(courses)
        if nothing_new and auto_commit:
            self.commit_scan(check_id)
        result = {
            "check_id": check_id,
            "checked_at": now.isoformat(timespec="minutes"),
            "previous_check": last_check,
            "semester": chosen,
            "excluded": sorted(excluded),
            "summary": (f"{len(attention)} of {len(courses)} courses need attention, "
                        f"{len(fresh_news)} news item(s) since the previous check"),
            "courses_with_changes": attention,
            "unchanged_courses": quiet,
            "upcoming_deadlines_14_days": upcoming,
            "news_since_previous_check": fresh_news,
            "requests_used": self.client.call_requests,
        }
        if news_notes:
            result["notes"] = news_notes
        if nothing_new and auto_commit:
            result["committed"] = True
            result["next_step"] = "nothing changed; already saved as the new baseline"
        else:
            result["next_step"] = "record the findings, then ilias_commit_scan(check_id)"
        return result

    def _last_check(self) -> str | None:
        path = self.snapshots / "last-check.json"
        try:
            return json.loads(path.read_text("utf-8")).get("checked_at")
        except (OSError, ValueError):
            return None

    def _commit_check(self, check_id: str, bundle_path: Path) -> dict:
        bundle = json.loads(bundle_path.read_text("utf-8"))
        committed, missing = [], []
        for scan_id in bundle["scan_ids"]:
            try:
                committed.append(self.commit_scan(scan_id)["course"])
            except ValueError:
                missing.append(scan_id)
        (self.snapshots / "last-check.json").write_text(json.dumps(
            {"checked_at": bundle["checked_at"], "committed_at": dates.now_berlin().isoformat(timespec="minutes")}),
            "utf-8")
        bundle_path.unlink()
        result: dict[str, Any] = {"committed": check_id, "courses": committed, "baseline_from": bundle["checked_at"]}
        if missing:
            result["already_committed_or_missing"] = missing
        return result
