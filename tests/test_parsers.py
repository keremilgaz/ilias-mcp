from datetime import datetime

import pytest

from ilias_mcp import dates, parsers

from .conftest import BASE, fixture

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=dates.BERLIN)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("3. Nov 2026, 14:05", "2026-11-03T14:05+01:00"),
        ("Deadline: 12. November 2026, 23:59 h", "2026-11-12T23:59+01:00"),
        ("20. Okt 2026, 08:00", "2026-10-20T08:00+02:00"),
        ("5. Mär. 2027", "2027-03-05"),
        ("Nov 5, 2026 2:30", "2026-11-05T02:30+01:00"),
        ("05.11.2026 14:00", "2026-11-05T14:00+01:00"),
        ("Today, 08:15", "2026-11-06T08:15+01:00"),
        ("Gestern, 18:20", "2026-11-05T18:20+01:00"),
        ("Morgen, 12:00", "2026-11-07T12:00+01:00"),
        ("Version: 2", None),
        ("6 days 23 hours", None),
    ],
)
def test_dates(text, expected) -> None:
    assert dates.find_date(text, now=NOW) == expected


def test_all_dates_in_order() -> None:
    assert dates.find_all_dates("20. Oct 2026 - 15. Feb 2027") == ["2026-10-20", "2027-02-15"]


def test_login_detection_and_form() -> None:
    login = fixture("login.html")
    assert parsers.is_login_page(login)
    assert not parsers.is_logged_in(login)
    assert parsers.is_logged_in(fixture("dashboard.html"))
    form = parsers.find_login_form(login, f"{BASE}/login.php?client_id=ILIASKONSTANZ&cmd=force_login")
    assert form is not None
    assert form.user_field == "login_form/input_3/input_4"
    assert form.password_field == "login_form/input_3/input_5"
    assert form.action.startswith(f"{BASE}/ilias.php?baseClass=ilStartUpGUI&cmd=post")


def test_dashboard_courses_with_semester_sections() -> None:
    items = parsers.parse_items(fixture("dashboard.html"), f"{BASE}/ilias.php")
    assert [(i["type"], i["ref_id"], i["section"]) for i in items] == [
        ("crs", "2125765", "Winter semester 2026"),
        ("crs", "2099965", "Winter semester 2026"),
        ("grp", "1990001", "Summer semester 2026"),
    ]
    assert items[0]["description"] == "Lecture, WiSe 2026/27"
    assert "Period: 20. Oct 2026 - 15. Feb 2027" in items[0]["properties"]


def test_course_items() -> None:
    items = parsers.parse_items(fixture("course.html"), f"{BASE}/ilias.php?ref_id=2125765")
    by_title = {i["title"]: i for i in items}
    assert set(by_title) == {"Lecture Content", "Organization", "Assignments", "Forum",
                             "05. Nov 2026, 10:00 - 11:30: Lecture 3"}
    assert by_title["Lecture Content"]["type"] == "fold"
    assert by_title["Lecture Content"]["section"] == "Content"
    org = by_title["Organization"]
    assert (org["type"], org["ref_id"], org["ext"], org["size"], org["version"], org["date"]) == (
        "file", "2131745", "pdf", "245.3 KB", 2, "2026-11-03T14:05+01:00"
    )
    assert by_title["Assignments"]["type"] == "exc"
    assert by_title["Forum"]["description"] == "Questions and answers"
    session = by_title["05. Nov 2026, 10:00 - 11:30: Lecture 3"]
    assert (session["type"], session["date"], session["section"]) == ("sess", "2026-11-05T10:00+01:00", "Sessions")


def test_sendfile_links_and_relative_dates() -> None:
    items = parsers.parse_items(fixture("folder.html"), f"{BASE}/ilias.php?ref_id=2131737")
    assert len(items) == 1
    assert items[0]["type"] == "file" and items[0]["ref_id"] == "2131770"
    assert items[0]["ext"] == "pptx" and items[0]["size"] == "3,1 MB"


def test_page_text_keeps_tables_drops_chrome() -> None:
    text = parsers.page_text(fixture("course.html"))
    assert "Exam registration in ZEuS until 30. Nov 2026, 23:59." in text
    assert "3 | Tool use" in text
    assert "Log Out" not in text
    assert "Add to Favourites" not in text
    for noise in ("Show advanced content", "Upload files", "Upcoming events", "Mo | Tu"):
        assert noise not in text


def test_assignments_show_all_view() -> None:
    html = fixture("exercise_all.html")
    found = parsers.parse_assignments(html, f"{BASE}/ilias.php")
    assert [a["ass_id"] for a in found] == ["501", "500"]
    a3, a2 = found
    assert a3["title"] == "Assignment 3: Literature Review"
    assert a3["deadline"] == "2026-11-12T23:59+01:00"
    assert a3["submitted"] is False
    assert a2["deadline"] == "2026-10-29T23:59+01:00"
    assert a2["last_submission"] == "2026-10-28T21:10+01:00"
    assert a2["submitted"] is True
    assert a2["files"][0]["name"] == "assignment2.pdf Download"


def test_assignments_legacy_german_accordion() -> None:
    found = parsers.parse_assignments(fixture("exercise_legacy.html"), f"{BASE}/ilias.php")
    assert len(found) == 1
    entry = found[0]
    assert entry["title"] == "Übungsblatt 1"
    assert entry["start"] == "2026-10-20T08:00+02:00"
    assert entry["deadline"].endswith("T12:00+01:00")
    assert entry["submitted"] is False


def test_show_all_link() -> None:
    url = parsers.find_show_all_url(fixture("exercise_default.html"), f"{BASE}/ilias.php")
    assert url and "mode=all" in url


def test_forum_thread_list() -> None:
    threads = parsers.parse_forum_threads(fixture("forum.html"), f"{BASE}/ilias.php")
    assert [t["thread_id"] for t in threads] == ["301", "300"]
    first = threads[0]
    assert first["title"] == "Question about Assignment 2"
    assert first["has_new"] is True
    assert first["columns"]["Posts"] == "4 (1 New)"
    assert threads[1]["last_activity"] == "2026-10-20T10:00+02:00"
    assert "has_new" not in threads[1]


def test_news() -> None:
    news = parsers.parse_news(fixture("news.html"), f"{BASE}/ilias.php")
    assert [n["news_id"] for n in news] == ["9911", "9900"]
    assert news[0]["title"] == "Room change on Thursday"
    assert news[0]["date"] == "2026-11-04T09:12+01:00"
    assert "Advances in Agentic AI" in news[0]["context"]


def test_ref_from_url() -> None:
    assert parsers.ref_from_url(f"{BASE}/goto.php/crs/12") == ("crs", "12")
    assert parsers.ref_from_url(f"{BASE}/goto_ILIASKONSTANZ_fold_34.html") == ("fold", "34")
    assert parsers.ref_from_url(f"{BASE}/goto.php?target=exc_56&client_id=X") == ("exc", "56")
    assert parsers.ref_from_url(f"{BASE}/ilias.php?baseClass=x&ref_id=78") == (None, "78")


def test_forum_ui_items_with_counts() -> None:
    threads = parsers.parse_forum_threads(fixture("forum_ui.html"), f"{BASE}/ilias.php")
    assert len(threads) == 1  # the sortation button (thr_pk=0) is not a thread
    thread = threads[0]
    assert (thread["title"], thread["posts"], thread["unread"]) == ("Final Submission", 3, 1)
    assert thread["columns"]["Angelegt von"] == "tutor.one"
    assert thread["last_activity"] == "2026-07-15T17:37+02:00"


@pytest.mark.parametrize(
    "label", ["Zu bearbeiten bis", "Abgabe bis", "Edit Until", "Deadline", "Beendet am", "Abgabetermin"]
)
def test_deadline_labels(label) -> None:
    html = (
        '<div id="ilContentContainer"><div class="il-item">'
        '<div class="il-item-title"><a href="ilias.php?ass_id=1&amp;cmdClass=ilAssignmentPresentationGUI">A1</a></div>'
        f'<div class="il-item-property-name">{label}</div>'
        '<div class="il-item-property-value">11. Nov 2026, 10:00</div>'
        '<div class="il-item-property-name">Startzeit</div><div class="il-item-property-value">1. Nov 2026, 10:00</div>'
        "</div></div>"
    )
    entry = parsers.parse_assignments(html, f"{BASE}/ilias.php")[0]
    assert entry["deadline"] == "2026-11-11T10:00+01:00"
    assert entry["start"] == "2026-11-01T10:00+01:00"


def test_page_links_skip_calendar_and_menus() -> None:
    links = parsers.page_links(fixture("course.html"), f"{BASE}/ilias.php")
    texts = {l["text"] for l in links}
    assert "Lecture Content" in texts
    assert not texts & {"Mo", "Tu", "Add to Favourites", "Upcoming events"}
