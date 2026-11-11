import json
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


def test_read_file_continues_a_long_page(service: IliasService, fake) -> None:
    text = "abcdefghij" * 250  # one 2500-character line: a single page
    fake.files["2131799"] = (text.encode(), "notes.txt")
    first = service.read_file("2131799", max_chars=1000)
    assert first["text"][0]["text"] == text[:1000]
    assert {k: first["continue_with"][k] for k in ("pages", "offset")} == {"pages": "1", "offset": 1000}
    assert first["remaining_pages"] == "1"  # not read yet

    second = service.read_file("2131799", max_chars=1000, **first["continue_with"])
    assert second["text"][0] == {"page": 1, "text": text[1000:2000], "offset": 1000}
    third = service.read_file("2131799", max_chars=1000, **second["continue_with"])
    assert third["text"][0]["text"] == text[2000:] and "continue_with" not in third
    assert service.read_file("2131799")["status"] == "already_read"  # its end was returned

    with pytest.raises(ValueError):
        service.read_file("2131799", pages="1", offset=5000)


def test_cache_is_separate_per_account(service: IliasService, fake, settings, client) -> None:
    from dataclasses import replace

    from ilias_mcp.client import IliasClient
    from ilias_mcp.files import FileCache

    fake.files["2131745"] = (make_pdf(["Max's copy"]), "org.pdf")
    service.crawl("crs/2125765")
    assert "Max's copy" in service.read_file("2131745")["text"][0]["text"]

    fake.users.add("erika.musterfrau")
    other_settings = replace(settings, username="erika.musterfrau")  # same cache_dir
    other_client = IliasClient(other_settings, transport=httpx.MockTransport(fake),
                               password_provider=lambda: conftest.PASSWORD, sleep=lambda s: None)
    other = IliasService(other_settings, other_client, FileCache(other_settings.account_dir / "files"))
    fake.files["2131745"] = (make_pdf(["Erika's copy"]), "org.pdf")
    other.crawl("crs/2125765")  # same ref_id and listing as Max's
    result = other.read_file("2131745")
    assert result["source"] == "downloaded" and "Erika's copy" in result["text"][0]["text"]
    assert other_settings.account_dir != settings.account_dir
    assert other.scan("crs/2125765")["note"].startswith("first scan")  # no shared snapshots


def _old_cache(base: Path) -> None:
    """The layout of version 0.2: no account recorded anywhere."""
    (base / "files" / "texts").mkdir(parents=True)
    (base / "files" / "index.json").write_text('{"files": {"2131745": {"versions": []}}}', "utf-8")
    (base / "snapshots" / "pending").mkdir(parents=True)
    (base / "snapshots" / "2125765.json").write_text("{}", "utf-8")
    (base / "routes.json").write_text("{}", "utf-8")


def test_old_cache_is_never_given_to_an_account_unasked(tmp_path) -> None:
    from ilias_mcp.config import Settings, adopt_legacy_cache, legacy_cache, prepare_cache

    base = tmp_path / "cache"
    _old_cache(base)
    first = Settings(username="someone.else", cache_dir=base)
    target = prepare_cache(first)  # what every server start does
    assert not (target / "files").exists() and legacy_cache(first)  # left where it was
    assert json.loads((target / "account.json").read_text("utf-8"))["username"] == "someone.else"

    kerem = Settings(username="Kerem.Ilgaz", cache_dir=base)
    service_dirs = prepare_cache(kerem)
    (service_dirs / "snapshots" / "pending").mkdir(parents=True)  # a server already started: empty dirs
    assert adopt_legacy_cache(kerem) == ["files", "snapshots", "routes.json"]
    assert service_dirs.name == "ilias.uni-konstanz.de-iliaskonstanz-kerem.ilgaz"
    assert (service_dirs / "files" / "index.json").exists() and not legacy_cache(kerem)


def test_adopting_refuses_to_merge_into_saved_data(tmp_path) -> None:
    from ilias_mcp.config import Settings, adopt_legacy_cache, prepare_cache

    base = tmp_path / "cache"
    _old_cache(base)
    settings = Settings(username="u", cache_dir=base)
    (prepare_cache(settings) / "snapshots").mkdir()
    (settings.account_dir / "snapshots" / "1.json").write_text("{}", "utf-8")
    with pytest.raises(ValueError):
        adopt_legacy_cache(settings)
    assert (base / "files" / "index.json").exists()  # nothing moved


def test_cli_cache_adopts_only_on_yes(tmp_path, monkeypatch, capsys) -> None:
    from ilias_mcp import install

    base = tmp_path / "cache"
    _old_cache(base)
    monkeypatch.setenv("ILIAS_CACHE_DIR", str(base))
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    with pytest.raises(SystemExit):
        install.main(["cache", "--user", "u", "--ask"])
    assert (base / "files").exists()
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    with pytest.raises(SystemExit) as done:
        install.main(["cache", "--user", "u", "--ask"])
    assert done.value.code == 0 and not (base / "files").exists()
    assert "adopted" in capsys.readouterr().out


def test_status_and_first_check_point_to_an_old_cache(service: IliasService, settings) -> None:
    _old_cache(Path(settings.cache_dir))
    assert "--adopt" in service.status()["old_cache"]
    check = service.check_all(exclude=["2099965"])
    assert any("--adopt" in n for n in check["notes"])


def test_narrower_scan_does_not_report_removals(service: IliasService) -> None:
    broad = service.scan("crs/2125765", depth=1)
    service.commit_scan(broad["scan_id"])
    narrow = service.scan("crs/2125765", depth=0, include_assignments=False, include_forums=False)
    assert narrow["removed"] == [] and "incomplete" not in narrow
    assert narrow["outside_scope_kept"] >= 3  # sub-folder items, assignments, threads
    service.commit_scan(narrow["scan_id"])
    again = service.scan("crs/2125765", depth=1)
    assert again["new"] == [] and again["removed"] == [] and again["changed"] == []


def test_narrower_scan_against_a_baseline_from_0_2(service: IliasService) -> None:
    service.commit_scan(service.scan("crs/2125765", depth=1)["scan_id"])
    path = service.snapshots / "2125765.json"
    data = json.loads(path.read_text("utf-8"))
    for sig in data["state"].values():
        sig.pop("_level", None)  # 0.2 recorded only the folder path
    path.write_text(json.dumps(data), "utf-8")
    assert service.scan("crs/2125765", depth=0)["removed"] == []


def test_news_point_stays_when_the_news_page_fails(service: IliasService, fake, monkeypatch) -> None:
    def at(day: int) -> None:
        monkeypatch.setattr(dates, "now_berlin", lambda: datetime(2026, 11, day, 9, 0, tzinfo=dates.BERLIN))

    at(1)
    service.commit_scan(service.check_all(exclude=["2099965"])["check_id"])
    at(5)
    fake.fail_when = lambda request: "ilpdnewsgui" in str(request.url).lower()
    partial = service.check_all(exclude=["2099965"])
    assert "committed" not in partial and any("news page" in n for n in partial["notes"])
    service.commit_scan(partial["check_id"])
    at(6)
    fake.fail_when = None
    later = service.check_all(exclude=["2099965"])
    assert later["previous_check"].startswith("2026-11-05")
    assert later["news_compared_with"].startswith("2026-11-01")
    assert "9900" in [n["news_id"] for n in later["news_since_previous_check"]]  # dated 4 Nov


def test_continuation_never_mixes_versions(service: IliasService, fake) -> None:
    old, new = "a" * 2500, "b" * 2500
    fake.files["2131799"] = (old.encode(), "notes.txt")
    first = service.read_file("2131799", max_chars=1000)
    assert first["continue_with"]["version"]

    fake.files["2131799"] = (new.encode(), "notes.txt")  # updated between the two calls
    second = service.read_file("2131799", max_chars=1000, **first["continue_with"])
    assert second["version_changed"] is True
    assert second["text"][0]["text"] == new[:1000] and "offset" not in second["text"][0]

    # Asking for the end of a version whose beginning was never returned: not read.
    tail = service.read_file("2131799", pages="1", offset=2000, max_chars=1000)
    assert tail["text"][0]["note"].startswith("starts in the middle")
    assert service.read_file("2131799", max_chars=1000).get("status") != "already_read"


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


def test_incomplete_scan_keeps_the_baseline(service: IliasService, fake) -> None:
    baseline = service.scan("crs/2125765", depth=1)
    assert "incomplete" not in baseline
    service.commit_scan(baseline["scan_id"])

    folder_page = fake.ref_pages.pop("2131737")  # the folder now fails to load
    later = service.scan("crs/2125765", depth=1)
    assert later["incomplete"] is True
    assert any("Lecture Content" in n for n in later["notes"])
    assert later["removed"] == []  # cannot tell deleted from unreachable
    assert "item:2131770" in {r["key"] for r in later["not_seen"]}
    assert service.commit_scan(later["scan_id"])["kept_unseen"] == len(later["not_seen"])

    fake.ref_pages["2131737"] = folder_page  # the folder opens again
    again = service.scan("crs/2125765", depth=1)
    assert "incomplete" not in again
    assert again["new"] == [] and again["removed"] == [] and again["changed"] == []


def test_complete_scan_still_reports_removals(service: IliasService, fake, monkeypatch) -> None:
    baseline = service.scan("crs/2125765", depth=1)
    service.commit_scan(baseline["scan_id"])
    folder = conftest.fixture("folder.html")
    assert "2131770" in folder
    real_fixture = conftest.fixture
    # The folder still opens but no longer lists anything: a real removal.
    monkeypatch.setattr(conftest, "fixture",
                        lambda name: "<html><body></body></html>" if name == "folder.html" else real_fixture(name))
    later = service.scan("crs/2125765", depth=1)
    assert "incomplete" not in later
    assert "item:2131770" in {r["key"] for r in later["removed"]}


def test_check_all_with_unreachable_folder(service: IliasService, fake) -> None:
    first = service.check_all(exclude=["2099965"])
    service.commit_scan(first["check_id"])
    folder_page = fake.ref_pages.pop("2131737")
    second = service.check_all(exclude=["2099965"])
    course = second["courses_with_changes"][0]
    assert course["incomplete"] is True and "removed" not in course and course["not_seen"]
    assert "committed" not in second  # incomplete: left to the caller
    service.commit_scan(second["check_id"])
    fake.ref_pages["2131737"] = folder_page
    third = service.check_all(exclude=["2099965"])
    assert third["courses_with_changes"] == [] and third["committed"] is True


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
    # Same source as ilias_list_news: the dashboard's news page, not the dashboard itself.
    assert [n["news_id"] for n in first["news_since_previous_check"]] == ["9911", "9900"]
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
