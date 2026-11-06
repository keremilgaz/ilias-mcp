"""HTML parsing for ILIAS pages.

Pure functions: an HTML string (plus the URL it came from) goes in, plain
dicts come out. Nothing here touches the network, so the module can be
hot-reloaded while the server runs and is easy to test against saved pages.

Selectors follow what ILIAS 8/9/10 render for the classic container list
(``il_ContainerListItem``), the UI framework (``il-item``, ``il-card``) and the
legacy accordions/blocks. When a parser finds nothing it says so instead of
guessing, and callers can fall back to :func:`page_text`.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from . import dates

# --------------------------------------------------------------------------
# basics


def soupify(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _has_class(tag: Tag, *names: str) -> bool:
    cls = _classes(tag)
    return any(n in cls for n in names)


def query_param(url: str, key: str) -> str | None:
    values = {k.lower(): v for k, v in parse_qs(urlsplit(url).query).items()}
    found = values.get(key.lower())
    return found[0] if found else None


_REF_PATTERNS = [
    re.compile(r"/goto\.php/(?P<type>[a-z]{2,5})/(?P<id>\d+)"),
    re.compile(r"/go/(?P<type>[a-z]{2,5})/(?P<id>\d+)"),
    re.compile(r"goto_.+?_(?P<type>[a-z]{2,5})_(?P<id>\d+)"),
    re.compile(r"[?&]target=(?P<type>[a-z]{2,5})_(?P<id>\d+)"),
]


def ref_from_url(url: str) -> tuple[str | None, str | None]:
    """(object type, ref_id) for an ILIAS link; either part may be None."""
    for pattern in _REF_PATTERNS:
        match = pattern.search(url)
        if match:
            return match["type"], match["id"]
    ref_id = query_param(url, "ref_id")
    return None, ref_id


# --------------------------------------------------------------------------
# login state


@dataclass
class LoginForm:
    action: str
    fields: dict[str, str]
    user_field: str
    password_field: str


def find_login_form(html: str, page_url: str) -> LoginForm | None:
    soup = soupify(html)
    for form in soup.find_all("form"):
        password = form.find("input", attrs={"type": re.compile("^password$", re.I)})
        if not password or not password.get("name"):
            continue
        user_field = None
        fields: dict[str, str] = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            kind = (inp.get("type") or "text").lower()
            if not name or kind in ("submit", "button", "image", "file", "reset"):
                continue
            if kind in ("checkbox", "radio") and not inp.has_attr("checked"):
                continue
            fields[name] = inp.get("value", "")
            if user_field is None and kind in ("text", "email") and inp is not password:
                user_field = name
        submit = form.find(["button", "input"], attrs={"type": re.compile("^submit$", re.I), "name": True})
        if submit is not None:
            fields[submit["name"]] = submit.get("value", "")
        if user_field is None:
            continue
        action = urljoin(page_url, form.get("action") or page_url)
        return LoginForm(action, fields, user_field, password["name"])
    return None


def is_login_page(html: str) -> bool:
    return find_login_form(html, "https://x/") is not None


def is_logged_in(html: str) -> bool:
    soup = soupify(html)
    if soup.find("input", attrs={"type": re.compile("^password$", re.I)}):
        return False
    if soup.find("a", href=re.compile(r"logout\.php|doLogout|cmd=logout", re.I)):
        return True
    metabar = soup.select_one(".il-maincontrols-metabar")
    if metabar is not None:
        login_link = metabar.find(attrs={"href": re.compile(r"login\.php", re.I)})
        return login_link is None and soup.find(id="button_shib_login") is None
    return False


def has_shibboleth_login(html: str) -> bool:
    soup = soupify(html)
    return bool(
        soup.find(id="button_shib_login") or soup.find("a", href=re.compile(r"shib_login|saml", re.I))
    )


# --------------------------------------------------------------------------
# page level


def page_title(html: str) -> str:
    soup = soupify(html)
    for selector in ("#il_mhead_t_focus", ".il-page-content-header", "h1.ilHeader", "h1"):
        tag = soup.select_one(selector)
        if tag and clean(tag.get_text()):
            return clean(tag.get_text())
    title = soup.find("title")
    return clean(title.get_text()) if title else ""


_NOISE = (
    "script", "style", "noscript", "nav", "footer", "form[name='login_form']",
    ".il-maincontrols", ".il-mainbar", ".il-metabar", ".il-maincontrols-metabar",
    ".dropdown-menu", ".ilAdminRow", ".il-layout-page-footer", ".sr-only",
    ".breadcrumb", ".il-breadcrumbs", ".ilFloatRight .btn", ".il-viewcontrol",
    "button", "dialog", ".modal", ".il-modal-roundtrip", ".il-dropzone", "template",
    "[id^=block_cal]", "table.calmini", ".ilNoDisplay", ".ilAccHidden",
    "[style*='display:none']", "[style*='display: none']",
)


def content_root(soup: BeautifulSoup) -> Tag:
    for selector in ("#ilContentContainer", "main", ".il-layout-page-content", "#mainspacekeeper"):
        tag = soup.select_one(selector)
        if tag is not None:
            return tag
    return soup.body or soup


def page_text(html: str) -> str:
    """Readable text of the page's main area: tables as `a | b` rows."""
    soup = soupify(html)
    root = content_root(soup)
    for selector in _NOISE:
        for tag in root.select(selector):
            tag.decompose()
    for row in root.select("tr"):
        cells = [clean(c.get_text(" ")) for c in row.find_all(["td", "th"], recursive=False)]
        row.replace_with(NavigableString("\n" + " | ".join(c for c in cells if c) + "\n"))
    for br in root.find_all("br"):
        br.replace_with(NavigableString("\n"))
    lines: list[str] = []
    for raw in root.get_text("\n").split("\n"):
        line = clean(raw)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


def page_links(html: str, page_url: str, limit: int = 150) -> list[dict]:
    """Links in the main area (minus action links), for following up."""
    soup = soupify(html)
    root = content_root(soup)
    seen: set[str] = set()
    out: list[dict] = []
    for a in root.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")) or "rtoken=" in href:
            continue
        url = urljoin(page_url, href)
        text = clean(a.get_text(" ")) or clean(a.get("title")) or clean(a.get("aria-label"))
        if not text or url in seen:
            continue
        seen.add(url)
        kind, ref_id = ref_from_url(url)
        entry = {"text": text[:160], "url": url}
        if ref_id:
            entry["ref_id"] = ref_id
        if kind:
            entry["type"] = kind
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def find_link(html: str, page_url: str, pattern: str) -> str | None:
    """First href matching ``pattern`` (regex, case-insensitive), absolute."""
    soup = soupify(html)
    rx = re.compile(pattern, re.I)
    for a in soup.find_all("a", href=True):
        if rx.search(a["href"]):
            return urljoin(page_url, a["href"])
    return None


# --------------------------------------------------------------------------
# container items (courses, folders, groups, sessions, dashboard)

_ICON_RX = re.compile(r"icon_([a-z]+)\.(?:svg|png|gif)", re.I)
_ICON_ALIASES = {"crsr": "crs", "grpr": "grp", "catr": "cat"}
_ALT_TYPES = {
    "folder": "fold", "ordner": "fold", "file": "file", "datei": "file",
    "exercise": "exc", "übung": "exc", "forum": "frm", "session": "sess",
    "sitzung": "sess", "course": "crs", "kurs": "crs", "group": "grp",
    "gruppe": "grp", "weblink": "webr", "link": "webr", "content page": "copa",
    "inhaltsseite": "copa", "test": "tst", "survey": "svy", "umfrage": "svy",
    "wiki": "wiki", "mediacast": "mcst", "blog": "blog",
}
_URL_TYPES = [
    (re.compile(r"cmd=sendfile|ilobjfilegui|/file/\d+/download", re.I), "file"),
    (re.compile(r"ilexercisehandlergui|ilobjexercisegui", re.I), "exc"),
    (re.compile(r"ilobjforumgui", re.I), "frm"),
    (re.compile(r"illinkresourcehandlergui", re.I), "webr"),
    (re.compile(r"ilobjsessiongui", re.I), "sess"),
    (re.compile(r"ilobjfoldergui", re.I), "fold"),
    (re.compile(r"ilobjgroupgui", re.I), "grp"),
    (re.compile(r"ilobjcoursegui", re.I), "crs"),
    (re.compile(r"ilobjcontentpagegui", re.I), "copa"),
]
_ITEM_ROOT_CLASSES = ("ilContainerListItemOuter", "il-std-item", "il-item", "il-card", "card")

_SIZE_RX = re.compile(r"\b(\d+(?:[.,]\d+)?\s?(?:[KMGT]i?B|Bytes?|B))\b", re.I)
_VERSION_RX = re.compile(r"\bVersion:?\s*(\d+)", re.I)
_EXT_RX = re.compile(r"^[A-Za-z0-9]{2,5}$")
_AVAILABILITY = re.compile(r"availab|verfügbar|zeitraum|period|visible|sichtbar", re.I)


def _item_root(link: Tag) -> Tag:
    for parent in link.parents:
        if isinstance(parent, Tag) and _has_class(parent, *_ITEM_ROOT_CLASSES):
            return parent
    for parent in link.parents:
        if isinstance(parent, Tag) and _has_class(parent, "il_ContainerListItem"):
            return parent
    return link.parent if isinstance(link.parent, Tag) else link


def _detect_type(url: str, root: Tag) -> str | None:
    kind, _ = ref_from_url(url)
    if kind:
        return _ICON_ALIASES.get(kind, kind)
    for rx, value in _URL_TYPES:
        if rx.search(url):
            return value
    for img in root.find_all("img"):
        match = _ICON_RX.search(img.get("src") or "")
        if match:
            name = match.group(1).lower()
            return _ICON_ALIASES.get(name, name)
        alt = clean(img.get("alt")).lower()
        if alt in _ALT_TYPES:
            return _ALT_TYPES[alt]
    return None


def _section_path(link: Tag) -> list[str]:
    """Item groups, blocks and accordions above ``link``, outermost first."""
    titles: list[str] = []
    for parent in link.parents:
        if not isinstance(parent, Tag):
            continue
        if _has_class(parent, "il-item-group"):
            head = parent.find(["h2", "h3", "h4"], recursive=False)
            if head is None:
                head = parent.select_one(".il-item-group-header, .il-item-group-title")
            if head is not None and clean(head.get_text()):
                titles.append(clean(head.get_text()))
        elif _has_class(parent, "ilContainerItemsContainer"):
            prev = parent.find_previous_sibling("div")
            if prev is not None and _has_class(prev, "ilContainerBlockHeader"):
                head = prev.find(["h2", "h3", "h4"])
                if head is not None and "sr-only" not in _classes(head):
                    titles.append(clean(head.get_text()))
        elif _has_class(parent, "il_VAccordionContentDef"):
            acc = parent.parent
            head = acc.find(class_=re.compile(r"ilc_va_ihead_|il_VAccordionHead")) if isinstance(acc, Tag) else None
            if head is not None:
                titles.append(clean(head.get_text()))
    return [t for t in reversed(titles) if t]


def _properties(root: Tag) -> list[str]:
    props: list[str] = []
    for span in root.select(".il_ItemProperties .il_ItemProperty, .il_ItemAlertProperty"):
        text = clean(span.get_text(" "))
        if text:
            props.append(text)
    if not props:
        holder = root.select_one(".il_ItemProperties")
        if holder is not None:
            props.extend(p for p in (clean(x) for x in holder.get_text("\n").split("\n")) if p)
    for name in root.select(".il-item-property-name"):
        value = name.find_next_sibling(class_="il-item-property-value")
        pair = f"{clean(name.get_text())}: {clean(value.get_text(' ')) if value else ''}".strip(": ")
        if pair:
            props.append(pair)
    seen: set[str] = set()
    return [p for p in props if not (p in seen or seen.add(p))]


def _description(root: Tag) -> str | None:
    tag = root.select_one(".il_Description, .il_Description_no_margin, .il-item-description")
    text = clean(tag.get_text(" ")) if tag else ""
    return text or None


def _file_info(props: list[str]) -> dict:
    info: dict = {}
    for prop in props:
        if "ext" not in info and _EXT_RX.match(prop) and not prop.isdigit():
            info["ext"] = prop.lower()
        if "size" not in info and (m := _SIZE_RX.search(prop)):
            info["size"] = m.group(1)
        if "version" not in info and (m := _VERSION_RX.search(prop)):
            info["version"] = int(m.group(1))
    return info


def _title_links(soup: BeautifulSoup) -> Iterable[Tag]:
    seen: set[int] = set()
    selectors = (
        "a.il_ContainerItemTitle",
        ".il_ContainerItemTitle a",
        ".il-item-title a",
        ".card-title a",
        "a.ilc_flist_a_FileListItemLink",
    )
    for selector in selectors:
        for a in soup.select(selector):
            if id(a) not in seen and a.get("href"):
                seen.add(id(a))
                yield a


def parse_items(html: str, page_url: str) -> list[dict]:
    """Objects listed on a container page, in page order, de-duplicated."""
    soup = soupify(html)
    root_area = content_root(soup)
    items: "OrderedDict[str, dict]" = OrderedDict()
    for link in _title_links(root_area):
        href = link["href"].strip()
        if href.startswith(("#", "javascript:")) or "rtoken=" in href or "news_id=" in href:
            continue
        url = urljoin(page_url, href)
        title = clean(link.get_text(" "))
        if not title:
            continue
        root = _item_root(link)
        kind = _detect_type(url, root)
        _, ref_id = ref_from_url(url)
        if "ilc_flist_a_FileListItemLink" in _classes(link):
            kind = "file"
            title = re.sub(r"\(\s*[\d.,]+\s*[KMGT]?B\s*\)\s*$", "", title).strip()
        props = _properties(root)
        item: dict = {"type": kind or "unknown", "title": title, "url": url}
        if ref_id:
            item["ref_id"] = ref_id
        section = _section_path(link)
        if section:
            item["section"] = " / ".join(section)
        description = _description(root)
        if description and description != title:
            item["description"] = description[:400]
        if props:
            item["properties"] = props
        when = None
        if kind == "file":
            when = dates.find_date(" | ".join(p for p in props if not _AVAILABILITY.search(p)))
        elif kind == "sess":
            when = dates.find_date(title) or dates.find_date(" | ".join(props))
        if when:
            item["date"] = when
        if kind == "file":
            item.update(_file_info(props))
        key = ref_id or url
        if key not in items:
            items[key] = item
    return list(items.values())


# --------------------------------------------------------------------------
# exercises

_DEADLINE_KEY = re.compile(
    r"deadline|edit until|ending on|ended on|end date|due|submission until|"
    r"abgabetermin|beendet am|frist|ende|\bbis\s*:?$", re.I
)
_START_KEY = re.compile(r"start|begin|available from|beginn|ab dem", re.I)
_LAST_SUB_KEY = re.compile(
    r"last submission|date of last submission|submitted on|submitted files|"
    r"letzte abgabe|datum der letzten abgabe|abgegebene dateien", re.I
)
_NOT_SUBMITTED = re.compile(
    r"no submission|not (?:yet )?submitted|nothing submitted|you have not|haven't submitted|"
    r"no files? (?:have been )?submitted|keine abgabe|nicht abgegeben|noch keine|keine datei|noch nicht", re.I
)
_GENERIC_LINK_TEXT = re.compile(
    r"^(submit|submission|hand in|abgeben|abgabe|show|anzeigen|download|herunterladen|open|öffnen|"
    r"details|more|mehr|edit|bearbeiten|team|feedback)\b", re.I
)


def find_show_all_url(html: str, page_url: str) -> str | None:
    return find_link(html, page_url, r"[?&]mode=all\b")


def _pairs(container: Tag) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for name in container.select(".il-item-property-name"):
        value = name.find_next_sibling(class_="il-item-property-value")
        pairs.append((clean(name.get_text(" ")), clean(value.get_text(" ")) if value else ""))
    for dt in container.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        pairs.append((clean(dt.get_text(" ")), clean(dd.get_text(" ")) if dd else ""))
    for label in container.select(".il_InfoScreenProperty, .il_InfoScreenPropertyName"):
        value = label.find_next_sibling(class_=re.compile("il_InfoScreenPropertyValue"))
        pairs.append((clean(label.get_text(" ")), clean(value.get_text(" ")) if value else ""))
    for group in container.select(".form-group, .ilFormRow"):
        label = group.find(["label"]) or group.select_one(".control-label")
        if label is None:
            continue
        name = clean(label.get_text(" "))
        value = clean(group.get_text(" "))[len(name):].strip(" :")
        pairs.append((name, value))
    for row in container.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            pairs.append((clean(cells[0].get_text(" ")), clean(cells[1].get_text(" "))))
    out, seen = [], set()
    for name, value in pairs:
        key = (name.rstrip(":"), value)
        if name and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _assignment_container(link: Tag, ass_id: str) -> Tag:
    best: Tag = link
    for parent in link.parents:
        if not isinstance(parent, Tag) or parent.name in ("body", "html", "[document]"):
            break
        ids = {
            query_param(a["href"], "ass_id")
            for a in parent.find_all("a", href=True)
            if "ass_id=" in a["href"]
        }
        if ids - {ass_id}:
            break
        best = parent
    return best


def _assignment_title(container: Tag, links: list[Tag]) -> str:
    for selector in (".il-item-title", ".panel-title", ".il-panel-title", "h2", "h3", "h4",
                     ".ilAssignmentHeader", ".il_VAccordionHead", "[class*=ilc_va_ihead]"):
        tag = container.select_one(selector)
        if tag is not None and clean(tag.get_text(" ")):
            return clean(tag.get_text(" "))
    for a in links:
        text = clean(a.get_text(" "))
        if text and not _GENERIC_LINK_TEXT.match(text):
            return text
    return ""


def parse_assignments(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    root = content_root(soup)
    groups: "OrderedDict[str, list[Tag]]" = OrderedDict()
    for a in root.find_all("a", href=True):
        if "rtoken=" in a["href"]:
            continue
        ass_id = query_param(a["href"], "ass_id")
        if ass_id:
            groups.setdefault(ass_id, []).append(a)
    result: list[dict] = []
    for ass_id, links in groups.items():
        # A table of contents may link every assignment; take the richest block.
        container = max(
            (_assignment_container(link, ass_id) for link in links),
            key=lambda tag: len(tag.get_text(" ")),
        )
        pairs = _pairs(container)
        text = page_text(str(container))
        entry: dict = {"ass_id": ass_id, "title": _assignment_title(container, links)}
        deadline = start = last_sub = None
        for name, value in pairs:
            when = dates.find_date(value)
            if when and deadline is None and _DEADLINE_KEY.search(name):
                deadline = when
            elif when and start is None and _START_KEY.search(name):
                start = when
            if last_sub is None and _LAST_SUB_KEY.search(name):
                last_sub = when or (value or None)
        if deadline is None:
            match = re.search(_DEADLINE_KEY.pattern + r"[^\n]{0,40}", text, re.I)
            if match:
                deadline = dates.find_date(match.group(0))
        if deadline:
            entry["deadline"] = deadline
        if start:
            entry["start"] = start
        if last_sub:
            entry["last_submission"] = last_sub
            entry["submitted"] = bool(dates.find_date(str(last_sub)))
        elif _NOT_SUBMITTED.search(text):
            entry["submitted"] = False
        if pairs:
            entry["properties"] = [f"{n}: {v}" if v else n for n, v in pairs][:25]
        files = []
        for a in container.find_all("a", href=True):
            href = a["href"]
            if "rtoken=" in href or not re.search(r"cmd=download|downloadfile|sendfile|file_id=", href, re.I):
                continue
            name = clean(a.get_text(" "))
            if _GENERIC_LINK_TEXT.match(name or "download"):
                row = a.find_parent(["tr", "li", "div"])
                name = clean(row.get_text(" ")) if row is not None else name
            files.append({"name": name[:160], "url": urljoin(page_url, href)})
        if files:
            entry["files"] = files
        entry["text"] = text[:1500]
        result.append(entry)
    return result


# --------------------------------------------------------------------------
# forums (thread list only; threads themselves are never opened)

_ROW_CLASSES = ("il-item", "il-std-item", "ilForumThreadRow", "list-group-item")
_POSTS_KEY = re.compile(r"^(posts|beitr|postings|replies|antworten)", re.I)
_POSTS_VALUE = re.compile(r"^(\d+)(?:\s*\((\d+)[^)]*\))?")


def _row(tag: Tag) -> Tag:
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in ("tr", "li") or _has_class(parent, *_ROW_CLASSES):
            return parent
    return tag.parent if isinstance(tag.parent, Tag) else tag


def _header_map(row: Tag) -> list[str]:
    table = row.find_parent("table")
    if table is None:
        return []
    head = table.find("thead")
    head_row = head.find("tr") if head else table.find("tr")
    if head_row is None or head_row is row:
        return []
    return [clean(c.get_text(" ")) for c in head_row.find_all(["th", "td"], recursive=False)]


def parse_forum_threads(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    threads: "OrderedDict[str, dict]" = OrderedDict()
    for a in soup.find_all("a", href=True):
        thr = query_param(a["href"], "thr_pk")
        if not thr:
            continue
        row = _row(a)
        entry = threads.get(thr)
        if entry is None:
            entry = {"thread_id": thr, "title": ""}
            threads[thr] = entry
            headers = _header_map(row) if row.name == "tr" else []
            cells = row.find_all(["td", "th"], recursive=False) if row.name == "tr" else []
            if headers and len(headers) == len(cells):
                entry["columns"] = {
                    h: clean(c.get_text(" ")) for h, c in zip(headers, cells) if h and clean(c.get_text(" "))
                }
            if "columns" not in entry:
                props = {}
                for name in row.select(".il-item-property-name"):
                    value = name.find_next_sibling(class_="il-item-property-value")
                    if value is not None and clean(name.get_text(" ")):
                        props[clean(name.get_text(" "))] = clean(value.get_text(" "))
                if props:
                    entry["columns"] = props
            for key, value in (entry.get("columns") or {}).items():
                if _POSTS_KEY.search(key) and (m := _POSTS_VALUE.match(value)):
                    entry["posts"] = int(m.group(1))
                    if m.group(2):
                        entry["unread"] = int(m.group(2))
            row_text = clean(row.get_text(" "))
            entry["row"] = row_text[:400]
            found = dates.find_all_dates(row_text)
            if found:
                entry["last_activity"] = found[-1]
            if re.search(r"\bnew\b|\bneu\b|unread|ungelesen", row_text, re.I):
                entry["has_new"] = True
        text = clean(a.get_text(" "))
        if text:
            # Prefer the thread link's text over "last posting" links (pos_pk).
            slot = "_post_titles" if query_param(a["href"], "pos_pk") else "_thread_titles"
            entry.setdefault(slot, []).append(text)
    result = []
    for entry in threads.values():
        candidates = entry.pop("_thread_titles", []) + entry.pop("_post_titles", [])
        entry["title"] = candidates[0] if candidates else ""
        result.append(entry)
    return result


# --------------------------------------------------------------------------
# news


def parse_news(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    news: "OrderedDict[str, dict]" = OrderedDict()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "rtoken=" in href:
            continue
        news_id = query_param(href, "news_id")
        if not news_id:
            continue
        title = clean(a.get_text(" "))
        entry = news.get(news_id)
        if entry is None:
            row = _row(a)
            row_text = clean(row.get_text(" "))
            entry = {"news_id": news_id, "title": title, "url": urljoin(page_url, href)}
            when = dates.find_date(row_text)
            if when:
                entry["date"] = when
            rest = row_text.replace(title, "", 1).strip(" -|:") if title else row_text
            if rest:
                entry["context"] = rest[:300]
            news[news_id] = entry
        elif not entry["title"] and title:
            entry["title"] = title
    return list(news.values())
