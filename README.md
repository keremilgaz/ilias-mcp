# ilias-mcp

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server
for the ILIAS learning platform of the University of Konstanz. It lets an MCP
client such as the Claude desktop app list your courses, folders, assignments,
forum topics and news, read course files, and report what changed since the
last check — without being able to change anything on ILIAS.

Built and tested against ILIAS 10 at `ilias.uni-konstanz.de` (German and
English UI). Other ILIAS 8–10 installations with a local login form should
work after setting `ILIAS_BASE_URL` and `ILIAS_CLIENT_ID`; Shibboleth-only
logins are not supported.

## Read-only is enforced, not promised

Every HTTP request, including each redirect hop, passes through
[`policy.py`](src/ilias_mcp/policy.py) before it leaves the machine:

| Rule | Why |
|---|---|
| `GET` only; a single `POST` is allowed for the login form, only during login and only to that exact URL | nothing can be submitted |
| No `rtoken` parameter | ILIAS attaches this CSRF token to links whose GET changes state (remove favourite, mark as read, leave, ...) |
| `cmd` / `fallbackCmd` must be on an allowlist of viewing commands | some state-changing GETs carry no `rtoken` (e.g. `setPdModeEvents` in the calendar block); unknown commands are refused and named, so a new safe one is added deliberately |
| No `thr_pk` / `pos_pk` | opening a forum thread marks its posts as read |
| No mail GUI | opening a mail marks it as read |
| Permanent links only in their plain `type/id` form | `goto` targets can carry suffixes such as registration codes that join a course |
| Same host, `https`, known entry points only | nothing slips through redirects |

There are no tools for submitting, posting, joining or team management.
Requests are spaced at least one second apart and every tool call has a
request budget. A rejected password is not retried, to avoid an account
lockout. The password is read from the macOS Keychain and never written to a
file, log or error message.

## Tools

| Tool | Returns |
|---|---|
| `ilias_list_courses` | courses and groups on the dashboard, grouped by semester |
| `ilias_list_items` | objects in a course/folder/session (type, ref_id, file version/date/size), optionally recursive |
| `ilias_list_assignments` | an exercise's assignments ("show all" view): deadline, start, submission status, files |
| `ilias_read_file` | text of PDF/PPTX/DOCX/text/ZIP files, per page or as keyword snippets; remembers what was read |
| `ilias_list_forum_topics` | the thread list with post counts and last activity; threads are never opened |
| `ilias_list_news` | dashboard or course news |
| `ilias_page_text` | readable text of any page (announcements, schedules), as a fallback |
| `ilias_scan` / `ilias_commit_scan` | new/changed/removed files, assignments, threads and page text since the last committed scan |
| `ilias_download_file` | save a file below `ILIAS_DOWNLOAD_ROOT`, never overwriting |
| `ilias_status` | configuration, login state, request counter and the active policy |

**Read record.** `ilias_read_file` keeps, per file and content hash, the pages
already returned. An unchanged, fully read file comes back as `already_read`
unless specific pages are requested, so the same PDF is not re-read every
week; a new upload is detected and read again.

**Change detection.** `ilias_scan` crawls one course and compares it with the
last *committed* snapshot. Commit only after the findings are recorded, so a
failed run never swallows changes. Forum unread counts are deliberately left
out of the comparison: reading a thread in the browser is not news.

## Setup (macOS)

```bash
git clone <this repository> ~/Projects/ilias-mcp
cd ~/Projects/ilias-mcp
bash setup.sh            # or: bash setup.sh --skip-check
```

The script

1. creates `.venv` and installs the package (Python 3.10+),
2. asks for your ILIAS username and stores the password in the Keychain
   (`security add-generic-password -w` prompts for it, so it never appears on
   screen or in the shell history),
3. runs a self-test (`ilias-mcp-check`: log in, open two courses),
4. optionally adds the server to `claude_desktop_config.json` (with a backup):

```json
{
  "mcpServers": {
    "ilias": {
      "command": "/Users/<you>/Projects/ilias-mcp/.venv/bin/ilias-mcp",
      "env": { "ILIAS_USER": "firstname.lastname", "ILIAS_DOWNLOAD_ROOT": "/Users/<you>/Documents/ILIAS" }
    }
  }
}
```

Restart the Claude app afterwards. Then ask, for example: *"Scan my Scientific
Practices course on ILIAS and list the upcoming deadlines."*

### Configuration

| Variable | Default |
|---|---|
| `ILIAS_USER` | required |
| `ILIAS_BASE_URL` | `https://ilias.uni-konstanz.de` |
| `ILIAS_CLIENT_ID` | `ILIASKONSTANZ` |
| `ILIAS_LANG` | `en` (the UI language of the session follows your ILIAS profile) |
| `ILIAS_MIN_INTERVAL` | `1.0` seconds between requests (minimum 0.5) |
| `ILIAS_MAX_REQUESTS_PER_CALL` | `60` (`ilias_scan` uses 120) |
| `ILIAS_KEYCHAIN_SERVICE` | `ilias-mcp` |
| `ILIAS_CACHE_DIR` | `~/Library/Caches/ilias-mcp` (read record, snapshots, extracted text) |
| `ILIAS_DOWNLOAD_ROOT` | `~/Documents/ILIAS` |

## Project layout

```
src/ilias_mcp/
  policy.py       the read-only request policy
  client.py       HTTP client: guarded transport, rate limit, request budget, login and re-login
  credentials.py  Keychain lookup
  parsers.py      HTML -> data (container lists, assignments, forum, news, page text); hot-reloaded
  dates.py        German/English ILIAS dates -> ISO 8601 (Europe/Berlin)
  files.py        text extraction (pypdf, PPTX/DOCX via zipfile) and the read record
  service.py      the operations behind the tools (crawl, scan, read, download)
  server.py       MCP wiring (stdio)
  check.py        ilias-mcp-check self-test
tests/            pytest suite against a fake ILIAS (httpx.MockTransport) and HTML fixtures
```

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The tests cover the policy, login and re-login, redirects into blocked URLs,
rate limiting, parsing, the read record, change detection and the MCP layer.
`ilias-mcp-check --dump DIR` saves the pages it fetched (with `rtoken` and
hidden form values blanked) to adapt the parsers to real markup; the running
server reloads `parsers.py` and `dates.py` when they change, so parser fixes
need no restart.

## Responsible use

This is a personal client for your own account. The University of Konstanz
ILIAS `robots.txt` asks automated crawlers to stay away; this tool is not a
crawler of the site, but it is automated, so keep the request rate low, scan
one course at a time and check your university's terms of use. Course
material is for your own study: do not republish it.

Selector knowledge comes from [PFERD](https://github.com/Garmelon/PFERD) and
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp).

## License

[MIT](LICENSE)
