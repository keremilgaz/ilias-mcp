from datetime import datetime
from pathlib import Path

import httpx
import pytest

from ilias_mcp import dates
from ilias_mcp.service import IliasService, target_url

from . import conftest
from .conftest import make_pdf, make_pptx


def test_target_forms() -> None:
    assert target_url("crs/123") == "/goto.php/crs/123"
    assert target_url("fold_9") == "/goto.php/fold/9"
    assert target_url("42") == "/ilias.php?baseClass=ilrepositorygui&ref_id=42"
    with pytest.raises(ValueError):
        target_url("not a target")


def test_list_courses(service: IliasService) -> None:
    result = service.list_courses()
    assert result["source"] == "dashboard"
    assert [c["title"] for c in result["courses"]] == [
        "Advances in Agentic AI", "Scientific Practices for Students", "Project Group"]


def test_crawl_with_depth(service: IliasService) -> None:
    result = service.crawl("crs/2125765", depth=1)
    titles = {(i["title"], i.get("path")) for i in result["items"]}
    assert ("L3 Tool Use", "Lecture Content") in titles
    assert result["page"]["ref_id"] == "2125765"


def test_crawl_skips_broken_branches(service: IliasService, fake) -> None:
    del fake.ref_pages["2131737"]  # the folder now answers 404
    result = service.crawl("crs/2125765", depth=1)
    assert any("Lecture Content" in e and "404" in e for e in result["errors"])
    assert ("Reading for Lecture 3", "05. Nov 2026, 10:00 - 11:30: Lecture 3") in {
        (i["title"], i.get("path")) for i in result["items"]}


def test_assignments_follow_show_all(service: IliasService, fake) -> None:
    result = service.assignments("exc/2104815")
    assert [a["ass_id"] for a in result["assignments"]] == ["501", "500"]
    assert any("mode=all" in str(r.url) for r in fake.requests)
    assert result["assignments"][1]["deadline_passed"] is True


def test_read_file_remembers_pages(service: IliasService, fake) -> None:
    fake.files["2131745"] = (make_pdf(["Organization", "Submit via ILIAS by 12 Nov", "Grading"]), "org.pdf")
    service.crawl("crs/2125765")  # records the listing (version 2, date, size)

    first = service.read_file("2131745")
    assert first["source"] == "downloaded"
    assert first["returned_pages"] == "1-3"
    assert "Submit via ILIAS" in first["text"][1]["text"]

    downloads = sum("sendfile" in str(r.url) for r in fake.requests)
    second = service.read_file("2131745")
    assert second["status"] == "already_read"
    assert second["previously_read"] == "1-3"
    assert sum("sendfile" in str(r.url) for r in fake.requests) == downloads  # served from cache

    again = service.read_file("2131745", pages="2")
    assert again["returned_pages"] == "2"

    hits = service.read_file("2131745", query="submit|grading")
    assert hits["pages_with_hits"] == "2-3"


def test_read_file_detects_new_version(service: IliasService, fake) -> None:
    fake.files["2131745"] = (make_pdf(["v1"]), "org.pdf")
    service.read_file("2131745")
    fake.files["2131745"] = (make_pdf(["v2 with new deadline"]), "org.pdf")
    second = service.read_file("2131745")  # not listed this process: downloads and compares
    assert second["source"] == "downloaded_new_version"
    assert "v2" in second["text"][0]["text"]


def test_read_pptx(service: IliasService, fake) -> None:
    fake.files["2131770"] = (make_pptx(["Agenda", "Tool use"]), "L3.pptx")
    result = service.read_file("2131770")
    assert result["kind"] == "pptx"
    assert [p["text"] for p in result["text"]] == ["Agenda", "Tool use"]


def test_forum_and_news(service: IliasService) -> None:
    forum = service.forum_topics("frm/2131742")
    assert len(forum["threads"]) == 2
    news = service.news()
    assert [n["news_id"] for n in news["news"]] == ["9911", "9900"]


def test_scan_reports_changes_only_after_commit(service: IliasService, fake, monkeypatch) -> None:
    monkeypatch.setattr(dates, "now_berlin", lambda: datetime(2026, 11, 6, 9, 0, tzinfo=dates.BERLIN))
    first = service.scan("crs/2125765", depth=1)
    assert first["note"].startswith("first scan")
    keys = {n["key"] for n in first["new"]}
    assert "item:2131745" in keys and "ass:2104815:501" in keys and "thr:2131742:301" in keys
    assert [d["key"] for d in first["upcoming_deadlines"]] == ["ass:2104815:501"]

    # Not committed yet: a second scan still reports everything as new.
    assert service.scan("crs/2125765", depth=1)["new"]

    third = service.scan("crs/2125765", depth=1)
    service.commit_scan(third["scan_id"])
    fourth = service.scan("crs/2125765", depth=1)
    assert fourth["new"] == [] and fourth["changed"] == [] and fourth["removed"] == []

    # The course page text (announcements) changes -> reported as a changed page.
    edited = conftest.fixture("course.html").replace("until 30. Nov 2026", "until 2. Dec 2026")
    real_fixture = conftest.fixture
    monkeypatch.setattr(conftest, "fixture", lambda name: edited if name == "course.html" else real_fixture(name))
    fifth = service.scan("crs/2125765", depth=1)
    assert [c["key"] for c in fifth["changed"]] == ["page:2125765"]


def test_download_stays_inside_root(service: IliasService, fake, settings) -> None:
    fake.files["2131745"] = (make_pdf(["x"]), "org.pdf")
    saved = service.download_file("2131745", "Agentic AI/ilias")
    path = Path(saved["saved_to"])
    assert path.exists() and settings.download_root.resolve() in path.parents
    assert service.download_file("2131745", "Agentic AI/ilias")["status"] == "already_present"
    with pytest.raises(ValueError):
        service.download_file("2131745", "/tmp/elsewhere")
    with pytest.raises(ValueError):
        service.download_file("2131745", "../../escape")


def test_incomplete_scan_is_flagged(service: IliasService, fake) -> None:
    baseline = service.scan("crs/2125765", depth=1)
    assert "incomplete" not in baseline
    service.commit_scan(baseline["scan_id"])
    del fake.ref_pages["2131737"]  # the folder now fails to load
    later = service.scan("crs/2125765", depth=1)
    assert later["incomplete"] is True
    assert any("Lecture Content" in n for n in later["notes"])
    assert "item:2131770" in {r["key"] for r in later["removed"]}  # why the warning matters


def test_learned_routes_skip_the_goto_redirect(service: IliasService, fake) -> None:
    service.crawl("crs/2125765", depth=1)
    first = len(fake.requests)
    service.crawl("crs/2125765", depth=1)
    second = fake.requests[first:]
    assert not any("/goto.php/" in str(r.url) for r in second)  # direct routes only
    assert len(second) < first - 1  # fewer requests than the first crawl (which also logged in)
    assignments = service.assignments("exc/2104815")  # learned from the first visit's redirect
    assert [a["ass_id"] for a in assignments["assignments"]] == ["501", "500"]


def test_broken_route_falls_back_to_goto(service: IliasService, fake) -> None:
    service.crawl("crs/2125765")
    service._routes["crs"]["params"].append(["broken", "1"])
    fake.fail_when = lambda request: "broken=1" in str(request.url)
    result = service.crawl("crs/2125765")
    assert result["page"]["ref_id"] == "2125765"
    assert any("/goto.php/crs/2125765" in str(r.url) for r in fake.requests[-3:])
    assert "broken" not in str(service._routes["crs"])  # relearned from the goto redirect


def test_latest_semester() -> None:
    from ilias_mcp.service import latest_semester
    assert latest_semester(["Sommersemester 2026", "Wintersemester 2025", "Wintersemester 2026"]) == "Wintersemester 2026"
    assert latest_semester(["Summer semester 2027", "Winter semester 2026"]) == "Summer semester 2027"
    assert latest_semester(["Courses"]) is None


def test_check_all_reports_only_changes(service: IliasService, fake, monkeypatch) -> None:
    monkeypatch.setattr(dates, "now_berlin", lambda: datetime(2026, 11, 6, 9, 0, tzinfo=dates.BERLIN))
    first = service.check_all(exclude=["crs/2099965"])
    assert first["semester"] == "Winter semester 2026"
    assert first["excluded"] == ["2099965"]
    assert [c["ref_id"] for c in first["courses_with_changes"]] == ["2125765"]  # first scan: all new
    assert [d["title"] for d in first["upcoming_deadlines_14_days"]] == ["Assignment 3: Literature Review"]
    service.commit_scan(first["check_id"])

    assert "committed" not in first  # changes found: the caller commits after recording

    second = service.check_all(exclude=["2099965"])
    assert second["courses_with_changes"] == []
    assert second["unchanged_courses"] == ["Advances in Agentic AI"]
    assert second["previous_check"] == first["checked_at"]
    assert second["committed"] is True  # quiet check: saved without another call
    with pytest.raises(ValueError):
        service.commit_scan(second["check_id"])  # already committed


def test_page_state_adopted_for_old_baselines(service: IliasService) -> None:
    import json as _json
    scan = service.scan("crs/2125765", depth=0)
    service.commit_scan(scan["scan_id"])
    path = service.snapshots / "2125765.json"
    data = _json.loads(path.read_text("utf-8"))
    data["state"] = {k: v for k, v in data["state"].items() if not k.startswith("page:")}
    path.write_text(_json.dumps(data), "utf-8")  # what a baseline from version 0.1 looks like
    again = service.scan("crs/2125765", depth=0)
    assert again["new"] == []
