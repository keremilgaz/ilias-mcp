import pytest

from ilias_mcp.policy import PolicyViolation, ReadOnlyPolicy

B = "https://ilias.uni-konstanz.de"
LOGIN_POST = (
    f"{B}/ilias.php?baseClass=ilStartUpGUI&cmd=post&fallbackCmd=doStandardAuthentication"
    "&lang=en&client_id=ILIASKONSTANZ"
)


@pytest.fixture
def policy() -> ReadOnlyPolicy:
    return ReadOnlyPolicy("ilias.uni-konstanz.de")


@pytest.mark.parametrize(
    "url",
    [
        f"{B}/goto.php/crs/2125765",
        f"{B}/goto.php/file/2131745/download",
        f"{B}/goto_ILIASKONSTANZ_crs_1396330.html",
        f"{B}/goto.php?target=fold_2131737&client_id=ILIASKONSTANZ",
        f"{B}/goto.php?target=file_2131745_download",
        f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=view&ref_id=2125765",
        f"{B}/ilias.php?baseClass=ilrepositorygui&cmdNode=zb:ow&cmdClass=ilObjFileGUI&cmd=sendfile&ref_id=1",
        f"{B}/ilias.php?baseClass=ilexercisehandlergui&cmdNode=dw:on&cmdClass=ilObjExerciseGUI"
        "&cmd=showOverview&ref_id=2104815&mode=all&from_overview=1",
        f"{B}/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems",
        f"{B}/ilias.php?baseClass=ilrepositorygui&cmdClass=ilobjforumgui&cmd=showThreads&ref_id=5",
        f"{B}/ilias.php?baseClass=ilDashboardGUI&cmdClass=ilPDNewsGUI&cmd=showNews&news_id=9",
        f"{B}/login.php?client_id=ILIASKONSTANZ&cmd=force_login&lang=en",
        f"{B}/data/ILIASKONSTANZ/mobs/mm_1/image.png",
    ],
)
def test_reads_are_allowed(policy: ReadOnlyPolicy, url: str) -> None:
    policy.check("GET", url)


@pytest.mark.parametrize(
    "url, reason",
    [
        (f"{B}/ilias.php?baseClass=ilDashboardGUI&cmd=removeFromDesk&ref_id=1&rtoken=abc", "rtoken"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=viewThread&ref_id=5&thr_pk=301", "forum thread"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=showThreads&ref_id=5&pos_pk=9", "forum posting"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=leave&ref_id=1", "leave"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=join&ref_id=1", "join"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd=markAllRead&ref_id=1", "markAllRead"),
        (f"{B}/ilias.php?baseClass=ilexercisehandlergui&cmd=submissionScreen&ass_id=1", "submissionScreen"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&fallbackCmd=deliver&ref_id=1", "deliver"),
        (f"{B}/ilias.php?baseClass=ilrepositorygui&cmd[delete]=1", "form command"),
        (f"{B}/ilias.php?baseClass=ilMailGUI&cmd=show", "mail"),
        (f"{B}/webdav.php/ILIASKONSTANZ/ref_1", "unknown ILIAS path"),
        (f"{B}/goto.php?target=crs_123_rcodeAbC123&client_id=ILIASKONSTANZ", "registration-code"),
        (f"{B}/goto_ILIASKONSTANZ_crs_123_rcodeAbC.html", "registration-code"),
        (f"{B}/goto.php?target=crs_123_join", "goto target"),
        (f"{B}/goto.php/crs/123/join", "unknown ILIAS path"),
        (f"{B}/logout.php?lang=en", "unknown ILIAS path"),
        ("https://evil.example/goto.php/crs/1", "another host"),
        ("http://ilias.uni-konstanz.de/goto.php/crs/1", "non-https"),
    ],
)
def test_state_changes_are_refused(policy: ReadOnlyPolicy, url: str, reason: str) -> None:
    with pytest.raises(PolicyViolation, match=reason):
        policy.check("GET", url)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "HEAD"])
def test_only_get_outside_login(policy: ReadOnlyPolicy, method: str) -> None:
    with pytest.raises(PolicyViolation):
        policy.check(method, f"{B}/goto.php/crs/1")


def test_login_post_only_inside_window_and_only_that_url(policy: ReadOnlyPolicy) -> None:
    with pytest.raises(PolicyViolation):
        policy.check("POST", LOGIN_POST)
    with policy.login_window(LOGIN_POST):
        policy.check("POST", LOGIN_POST)
        # parameter order does not matter, but the target does
        policy.check(
            "POST",
            f"{B}/ilias.php?client_id=ILIASKONSTANZ&lang=en&fallbackCmd=doStandardAuthentication"
            "&cmd=post&baseClass=ilStartUpGUI",
        )
        with pytest.raises(PolicyViolation):
            policy.check("POST", f"{B}/ilias.php?baseClass=ilExSubmissionGUI&cmd=post&ref_id=1")
    with pytest.raises(PolicyViolation):
        policy.check("POST", LOGIN_POST)
