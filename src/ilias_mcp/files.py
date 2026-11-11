"""Text extraction for course files and the record of what was already read.

The cache keeps, per ILIAS ref_id, every content version seen (by SHA-256),
its extracted text and which pages have already been handed out. That makes
"don't re-read the same PDF" a property of the tool instead of a habit:
an unchanged file comes back as ``already_read`` unless pages are asked for
explicitly.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from . import dates

TEXT_EXTENSIONS = {
    "txt", "md", "csv", "tsv", "json", "tex", "py", "java", "js", "ts", "r", "sql",
    "xml", "html", "htm", "yaml", "yml", "ipynb", "bib", "log",
}
CHARS_PER_TEXT_PAGE = 3000
MAX_ZIP_ENTRIES = 40


# --------------------------------------------------------------------------
# extraction


def detect_kind(content: bytes, filename: str | None) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    if content[:5] == b"%PDF-" or content[:1024].find(b"%PDF-") >= 0:
        return "pdf"
    if content[:4] == b"PK\x03\x04":
        try:
            names = zipfile.ZipFile(io.BytesIO(content)).namelist()
        except zipfile.BadZipFile:
            return "binary"
        if "word/document.xml" in names:
            return "docx"
        if any(n.startswith("ppt/slides/slide") for n in names):
            return "pptx"
        return "zip"
    if ext in TEXT_EXTENSIONS or _looks_textual(content):
        return "text"
    return "binary"


def _looks_textual(content: bytes) -> bool:
    sample = content[:4096]
    if not sample or b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _tidy(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_pages(content: bytes, kind: str) -> list[str]:
    """Text per page (PDF), per slide (pptx), per entry (zip) or per chunk."""
    if kind == "pdf":
        return _pdf_pages(content)
    if kind == "pptx":
        return _pptx_pages(content)
    if kind == "docx":
        return _chunk(_docx_text(content))
    if kind == "text":
        return _chunk(content.decode("utf-8", "replace"))
    if kind == "zip":
        return _zip_pages(content)
    return []


def _pdf_pages(content: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ["[encrypted PDF: text not available]"]
    pages = []
    for page in reader.pages:
        try:
            pages.append(_tidy(page.extract_text() or ""))
        except Exception as exc:  # broken page; keep going
            pages.append(f"[text of this page could not be extracted: {type(exc).__name__}]")
    return pages


def _xml_text(xml: str, tag: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m) for m in re.findall(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", xml, re.S)]


def _pptx_pages(content: bytes) -> list[str]:
    archive = zipfile.ZipFile(io.BytesIO(content))
    slides = sorted(
        (n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
        key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)),
    )
    pages = []
    for name in slides:
        xml = archive.read(name).decode("utf-8", "replace")
        paragraphs = [" ".join(_xml_text(p, "a:t")) for p in re.findall(r"<a:p>(.*?)</a:p>", xml, re.S)]
        pages.append(_tidy("\n".join(p for p in paragraphs if p.strip())))
    return pages


def _docx_text(content: bytes) -> str:
    xml = zipfile.ZipFile(io.BytesIO(content)).read("word/document.xml").decode("utf-8", "replace")
    paragraphs = ["".join(_xml_text(p, "w:t")) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    return "\n".join(p for p in paragraphs if p.strip())


def _chunk(text: str) -> list[str]:
    text = _tidy(text)
    if not text:
        return []
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) > CHARS_PER_TEXT_PAGE and current:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _zip_pages(content: bytes) -> list[str]:
    archive = zipfile.ZipFile(io.BytesIO(content))
    entries = [i for i in archive.infolist() if not i.is_dir()]
    pages = ["Archive contents:\n" + "\n".join(f"{i.filename} ({i.file_size} B)" for i in entries)]
    for info in entries[:MAX_ZIP_ENTRIES]:
        if info.file_size > 20 * 1024 * 1024:
            continue
        data = archive.read(info)
        kind = detect_kind(data, info.filename)
        if kind in ("pdf", "pptx", "docx", "text"):
            inner = extract_pages(data, kind)
            body = "\n\n".join(f"[{kind} page {n}]\n{t}" for n, t in enumerate(inner, 1)) if inner else ""
            pages.append(f"== {info.filename} ==\n{body}".strip())
    return pages


# --------------------------------------------------------------------------
# page selection and search


def parse_page_spec(spec: str | None, count: int) -> list[int]:
    """'1-3,7' -> [1, 2, 3, 7] (1-based, clipped to the document)."""
    if not spec:
        return list(range(1, count + 1))
    pages: list[int] = []
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            start = int(lo) if lo else 1
            end = int(hi) if hi else count
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    seen: set[int] = set()
    return [p for p in pages if 1 <= p <= count and not (p in seen or seen.add(p))]


def compact_ranges(pages: list[int]) -> str:
    """[1, 2, 3, 7] -> '1-3,7'."""
    out: list[str] = []
    start = prev = None
    for page in sorted(set(pages)):
        if start is None:
            start = prev = page
        elif page == prev + 1:
            prev = page
        else:
            out.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = page
    if start is not None:
        out.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(out)


def search_pages(pages: dict[int, str], query: str, context: int = 220) -> list[dict]:
    """Snippets around each keyword hit. Keywords split on '|' or ','."""
    terms = [t.strip() for t in re.split(r"[|,]", query) if t.strip()]
    if not terms:
        return []
    rx = re.compile("|".join(re.escape(t) for t in terms), re.I)
    hits: list[dict] = []
    for number, text in pages.items():
        spans: list[tuple[int, int]] = []
        for match in rx.finditer(text):
            start, end = max(0, match.start() - context), min(len(text), match.end() + context)
            if spans and start <= spans[-1][1]:
                spans[-1] = (spans[-1][0], end)
            else:
                spans.append((start, end))
        for start, end in spans:
            hits.append({"page": number, "snippet": text[start:end].replace("\n", " ")})
    return hits


# --------------------------------------------------------------------------
# cache / read record


class FileCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.texts = self.root / "texts"
        self.texts.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.index: dict[str, Any] = {"files": {}}
        if self.index_path.exists():
            try:
                self.index = json.loads(self.index_path.read_text("utf-8"))
            except (OSError, ValueError):
                self.index_path.replace(self.index_path.with_suffix(".corrupt.json"))
        self.index.setdefault("files", {})

    def _save(self) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.index, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(self.index_path)

    def _file(self, ref_id: str) -> dict:
        return self.index["files"].setdefault(str(ref_id), {"versions": []})

    def remember_listing(self, ref_id: str, title: str, listing: dict) -> None:
        record = self._file(ref_id)
        if record.get("listing") != listing or record.get("title") != title:
            record["title"] = title
            record["listing"] = listing
            self._save()

    def version_count(self, ref_id: str) -> int:
        record = self.index["files"].get(str(ref_id))
        return len(record["versions"]) if record else 0

    def last_listing(self, ref_id: str) -> dict | None:
        record = self.index["files"].get(str(ref_id))
        return record.get("listing") if record else None

    def version(self, ref_id: str, sha256: str | None = None, listing: dict | None = None) -> dict | None:
        record = self.index["files"].get(str(ref_id))
        if not record:
            return None
        for entry in reversed(record["versions"]):
            if sha256 is not None and entry["sha256"] == sha256:
                return entry
            if sha256 is None and listing and entry.get("listing") == listing:
                return entry
        return None

    def store(self, ref_id: str, content: bytes, filename: str | None, listing: dict | None) -> dict:
        sha = hashlib.sha256(content).hexdigest()
        existing = self.version(ref_id, sha256=sha)
        if existing is not None:
            if listing and existing.get("listing") != listing:
                existing["listing"] = listing
                self._save()
            return existing
        kind = detect_kind(content, filename)
        pages = extract_pages(content, kind)
        (self.texts / f"{sha}.json").write_text(json.dumps(pages, ensure_ascii=False), "utf-8")
        entry = {
            "sha256": sha,
            "filename": filename,
            "kind": kind,
            "bytes": len(content),
            "pages": len(pages),
            "listing": listing,
            "first_seen": dates.now_berlin().isoformat(timespec="minutes"),
            "read_pages": [],
        }
        self._file(ref_id)["versions"].append(entry)
        self._save()
        return entry

    def pages(self, sha256: str) -> list[str]:
        return json.loads((self.texts / f"{sha256}.json").read_text("utf-8"))

    def mark_read(self, ref_id: str, sha256: str, pages: list[int]) -> None:
        entry = self.version(ref_id, sha256=sha256)
        if entry is None:
            return
        entry["read_pages"] = sorted(set(entry["read_pages"]) | set(pages))
        entry["last_read"] = dates.now_berlin().isoformat(timespec="minutes")
        self._save()

    def status(self, ref_id: str, listing: dict | None) -> dict | None:
        """How much of this file (as currently listed) was read before."""
        record = self.index["files"].get(str(ref_id))
        if not record or not record["versions"]:
            return None
        entry = self.version(ref_id, listing=listing) if listing else None
        if entry is None:
            latest = record["versions"][-1]
            return {"read": "older_version_only", "last_read": latest.get("last_read")}
        read = entry["read_pages"]
        state = "full" if entry["pages"] and len(read) >= entry["pages"] else ("partial" if read else "no")
        out = {"read": state, "pages": entry["pages"]}
        if read:
            out["read_pages"] = compact_ranges(read)
            out["last_read"] = entry.get("last_read")
        return out


def listing_signature(item: dict) -> dict:
    """What the container listing says about a file version."""
    return {k: item[k] for k in ("version", "date", "size") if item.get(k) is not None}
