# ilias-mcp

**Ask your AI assistant about your ILIAS courses.**

Find course materials, check assignment deadlines, and catch up on what changed
since your last saved check, all from your AI chat.

An independent student project for the **University of Konstanz**. Connect
Claude to the course content you can access with your own ILIAS account.
Access is read-only: there are no tools for submitting assignments, posting
messages, or joining courses.

## What can I ask?

- “What assignments are due this week in my courses?”
- “What has changed in this course since my last check?”
- “Find the latest lecture slides and summarize them for me.”
- “Show me the announcements and forum topics for this course.”

The assistant retrieves information through ilias-mcp and uses it to answer
your question.

## Get started on macOS

You will need:

- The **Claude desktop app** and your **ILIAS login**.
- **Git** and **Python 3.10+** installed. The script can also use `uv`.

Open Terminal and run:

```bash
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
bash setup.sh
```

Follow the prompts to install the program, save your password in macOS
Keychain, and check the connection. The check opens two of your courses.
Choose a download folder and answer **y** when asked to add ilias-mcp to
Claude. Your existing configuration is backed up first.

Quit Claude completely with **Cmd+Q**, open it again, and try:

> List my courses on ILIAS.

## Get started on Windows

You will need the same: the **Claude desktop app**, your **ILIAS login**,
**Git**, and **Python 3.10+** from [python.org](https://www.python.org/downloads/)
(or `winget install Python.Python.3.12`).

Open PowerShell and run:

```powershell
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The prompts are the same as on macOS; your password is saved in **Windows
Credential Manager**. `-ExecutionPolicy Bypass` applies to this one run only.
Then quit Claude from its tray icon (closing the window is not enough), open
it again, and try the same question. Windows support is new: if something
fails, please open an issue.

## How does it work?

The program runs on your computer and retrieves ILIAS pages or files when
your assistant asks for them. It saves previous checks locally so later
scans can report changes. Checks run on request; there are no automatic
background notifications.

**MCP** stands for [Model Context Protocol](https://modelcontextprotocol.io).
It lets compatible AI apps use tools like this one. Manual configuration for
other MCP clients is included below.

## Your account and course data

- Your password stays in **macOS Keychain** or **Windows Credential Manager**,
  outside the AI configuration.
- Saved checks and extracted file text are cached on your computer.
- Retrieved content is shared with your **AI application** and may reach its
  cloud model provider. Local installation does not make the AI processing local.

## Current scope

An early release for Konstanz's ILIAS 10, with German and English support.
Other installations may need adaptation; Shibboleth/SSO login is unsupported.
It reads text from PDF, PowerPoint, Word, text files, and ZIP archives. Scanned
images need OCR, which is not included. Forum access covers topic lists.

## Technical reference

<details>
<summary><strong>Configuration and manual setup</strong></summary>

The setup script creates this entry in `claude_desktop_config.json`. For
manual setup, replace the example paths and username with your own:

```json
{
  "mcpServers": {
    "ilias": {
      "command": "/Users/<you>/Projects/ilias-mcp/.venv/bin/ilias-mcp",
      "env": {
        "ILIAS_USER": "firstname.lastname",
        "ILIAS_DOWNLOAD_ROOT": "/Users/<you>/Documents/ILIAS"
      }
    }
  }
}
```

On Windows the command is `C:\\Users\\<you>\\ilias-mcp\\.venv\\Scripts\\ilias-mcp.exe`
(backslashes doubled in JSON). `ilias-mcp-config add --user firstname.lastname --dry-run`,
run from the virtualenv, prints the exact entry for your computer; without
`--dry-run` it adds it, keeping your other servers and making a backup.

| System | Location of `claude_desktop_config.json` |
|---|---|
| macOS | `~/Library/Application Support/Claude/` |
| Windows | `%APPDATA%\Claude\`; Microsoft Store version: `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\` |

On Windows and Linux the password is read through
[`keyring`](https://pypi.org/project/keyring/); save it with
`.venv\Scripts\python -m keyring set ilias-mcp firstname.lastname`
(Linux: `.venv/bin/python`). Linux needs a running Secret Service such as GNOME Keyring.

If setup reports a failed connection check, inspect `selftest-report.json`.
To skip that check when running setup again, use `bash setup.sh --skip-check`
(Windows: `setup.ps1 -SkipCheck`).

| Variable | Default |
|---|---|
| `ILIAS_USER` | Required |
| `ILIAS_BASE_URL` | `https://ilias.uni-konstanz.de` |
| `ILIAS_CLIENT_ID` | `ILIASKONSTANZ` |
| `ILIAS_LANG` | `en`; the session UI language follows your ILIAS profile |
| `ILIAS_MIN_INTERVAL` | `1.0` seconds between requests; minimum `0.5` |
| `ILIAS_MAX_REQUESTS_PER_CALL` | `60`; `ilias_scan` uses `120`, `ilias_check_all` `400` |
| `ILIAS_TIMEOUT` | `30.0` seconds |
| `ILIAS_KEYCHAIN_SERVICE` | `ilias-mcp` |
| `ILIAS_CACHE_DIR` | `~/Library/Caches/ilias-mcp` on macOS, `%LOCALAPPDATA%\ilias-mcp\Cache` on Windows |
| `ILIAS_DOWNLOAD_ROOT` | `~/Documents/ILIAS` |

</details>

<details>
<summary><strong>Available tools and saved state</strong></summary>

| Tool | Returns |
|---|---|
| `ilias_list_courses` | Courses and groups on the dashboard, with semester sections |
| `ilias_list_items` | Course, folder, or session contents and file metadata; optionally recursive |
| `ilias_list_assignments` | Assignment deadlines, start dates, submission status, and files |
| `ilias_read_file` | Extracted file text, selected pages, or keyword snippets; long pages continue with `offset` |
| `ilias_list_forum_topics` | Thread titles, post counts, and last activity; does not open threads |
| `ilias_list_news` | Dashboard or course news |
| `ilias_page_text` | Readable page text as a fallback for announcements or schedules |
| `ilias_check_all` | All courses of the current semester in one call: only what changed, deadlines in the next 14 days, and new news. Runs in the background; call again while it reports `running` |
| `ilias_scan` | New, changed, and removed items compared with the saved course state |
| `ilias_commit_scan` | Saves a scan, or a whole check by its `check_id`, as the reference for the next comparison |
| `ilias_download_file` | Saves a file under the configured download folder without replacing a different file |
| `ilias_status` | Configuration, login state, request counter, and request policy |

**Reading records.** `ilias_read_file` tracks returned pages by file ID and
content hash. An unchanged, fully read version returns `already_read`.
Request specific `pages`, use a keyword `query`, or set `force=true` to read
it again. A page longer than `max_chars` is cut; the answer then names the
`pages` and `offset` that continue it, and the page counts as read once its
end has been returned. “Read” means the text was returned by the tool, not
that the user has read it.

**Change detection.** `ilias_scan` compares one course with its last committed
snapshot, then saves a pending snapshot and returns a `scan_id`. Calling
`ilias_commit_scan` with that ID replaces the course's comparison baseline.
The first scan treats all items as new. When part of a course cannot be
opened, the scan is marked `incomplete`: items it could not reach are listed
as `not_seen` instead of removed, and committing keeps them in the baseline
until a complete scan shows whether they still exist. Forum unread counts are
excluded from the comparison.

**Cache.** Reading records, extracted text, snapshots and learned routes are
kept per ILIAS installation and account, under `accounts/` in the cache
directory, so two accounts on one computer never share them. A cache from
version 0.2 or older is moved into the first account that starts. Clearing the
cache resets the saved history.

</details>

<details>
<summary><strong>Request policy, code layout, and development</strong></summary>

Every outgoing HTTP request, including redirects, is checked by
[`policy.py`](src/ilias_mcp/policy.py). Requests are paced at one per second
by default, with a budget per tool call. A rejected password is not
automatically retried.

| Check | Purpose |
|---|---|
| `GET` requests, with a login-only `POST` exception | Restricts form submissions to the login flow |
| Reject `rtoken` parameters | Blocks links carrying ILIAS action tokens |
| Allowlisted `cmd` / `fallbackCmd` values | Rejects unknown commands, including actions without an `rtoken` |
| Reject `thr_pk`, `pos_pk`, and the mail GUI | Avoids opening threads or mail that can mark content as read |
| Plain permanent-link targets only | Rejects registration-code links and other action suffixes |
| HTTPS, configured host, and known entry points | Restricts destinations, including redirect hops |

The code separates ILIAS access from the MCP interface:

```text
src/ilias_mcp/
  policy.py       Request checks
  client.py       HTTP requests, login, sessions, rate limits, and budgets
  credentials.py  Keychain / Credential Manager access
  parsers.py      HTML parsing
  dates.py        German/English dates in Europe/Berlin
  files.py        Text extraction and reading records
  service.py      Course scanning, comparisons, reading, and downloads
  server.py       MCP tools over stdio
  check.py        Live connection self-test
  install.py      Claude configuration (ilias-mcp-config)
tests/           Fake ILIAS server and HTML fixtures
```

To run the development tests:

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

On Windows, use `.venv\Scripts\pip` and `.venv\Scripts\pytest`.

Tests use `httpx.MockTransport` and HTML fixtures. They cover request checks,
login and re-login, redirects, rate limits, parsing, reading records, change
detection, and MCP tool calls.

For live parser debugging, `ilias-mcp-check --dump DIR` saves fetched pages
and attempts to redact action tokens and hidden form values. These pages
and the self-test report can still contain private course information; they
are excluded from Git by default when using the setup script's output paths.
The running server reloads `parsers.py` and `dates.py` when they change.

</details>

## Feedback and contributions

If you try it, feedback on setup, missing information, or a useful study
workflow is welcome. Open an
[issue](https://github.com/keremilgaz/ilias-mcp/issues) with what you expected
and what happened. Remove account details and private course content from
anything you share.

Use the tool with your own account, keep scans focused on your courses, and
follow your university's rules for automated access and course materials.

## Acknowledgements and license

Selector knowledge comes from [PFERD](https://github.com/Garmelon/PFERD) and
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp).

Licensed under [MIT](LICENSE).
