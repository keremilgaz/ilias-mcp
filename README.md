# ilias-mcp

**English** · [Türkçe](README.tr.md) · [Deutsch](README.de.md)

**Ask your AI assistant about your ILIAS courses.**

Find course materials, check assignment deadlines, and catch up on what changed
since your last saved check, all from your AI chat.

An independent student project for the **University of Konstanz**. Connect
your MCP client to the course content you can access with your own ILIAS account.
Access is read-only: there are no tools for submitting assignments, posting
messages, or joining courses.

## What can I ask?

- “What assignments are due this week in my courses?”
- “What has changed in this course since my last check?”
- “Find the latest lecture slides and summarize them for me.”
- “Show me the announcements and forum topics for this course.”

The assistant retrieves information through ilias-mcp and uses it to answer
your question.

## Usage scenarios

**Weekly check.** Once a week, ask:

> Check all my ILIAS courses for this semester and tell me what is new since my last check.

The assistant checks every course of the current semester in one go. It
reports only new or changed files, assignments, forum topics and
announcements, plus deadlines in the next 14 days. After you have noted what
matters, it saves the check, so next week's check starts from there. The very
first check lists everything as new.

**Deadlines at a glance.**

> List all open assignments with their deadlines, sorted by date, and mark the ones due this week.

It reads the exercise pages of your courses: deadlines, start dates and
whether you have already handed something in. If your assistant is also
connected to a calendar or to-do app, it can carry the dates over there.

**Preparing for a lecture.**

> Find the slides for the next Statistics lecture, summarize them and suggest three questions I could ask.

It finds the newest file in the course and works with its text. Pages already
read are remembered, so a later request returns only what is new.

**Tasks that appear only in PDFs.** Some instructions are only in slides or
handouts:

> Search this semester's course PDFs for submission, deadline or presentation and list what you find.

A keyword search returns the matching passages with page numbers instead of
whole documents.

**Catching up after a break.**

> I missed two weeks of the seminar. What changed in the course, and what did the announcements say?

It compares the course with your last saved check, shows new material and
announcements, and lists active forum topics. Threads are not opened, so
nothing is marked as read.

**Saving materials to your folder.**

> Download the new slides of this course into my ILIAS folder, under "Statistics".

Files are saved only inside your configured download folder, and a different
file with the same name is never overwritten.

**Exam preparation.**

> Go through all lecture slides of this course and build a list of topics, with the slides each one appears on.

Files are read one after another; long ones in parts. The reading record keeps
track of what has been covered, also across conversations.

What it does not do: submit assignments, write in forums, register for
courses or open forum threads.

## Install in Claude Desktop

1. Download `ilias-mcp-<version>.mcpb` from [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases).
2. In Claude Desktop, go to **Settings → Desktop app → Manage Extensions → Advanced settings → Install Extension** and select the bundle.
3. In a Claude chat, say **Open ILIAS setup**. Enter your credentials in the local browser form, then ask Claude to list your courses.

Claude Desktop manages Python and the dependencies on the first launch. If you
already saved your account with the setup script, you can ask for your courses
right away. When switching from a manual installation, disable the old ILIAS
entry in Claude Desktop so you see a single set of tools.
[Claude Desktop extension instructions](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

On Linux, have an unlocked Secret Service keyring in the same user session.
After changing a previously used account or password, restart Claude Desktop.

## Connect in ChatGPT

1. Create or find a tunnel in [OpenAI Platform](https://platform.openai.com/settings/organization/tunnels), associate it with your ChatGPT workspace, and create a runtime API key with **Tunnels Read + Use**. Download and extract the [official tunnel-client](https://github.com/openai/tunnel-client/releases/latest) for your system.
2. Run the command for your system from the extracted ILIAS source archive or repository. If `tunnel-client` is on your `PATH`, omit the executable path argument.

   **macOS and Linux**

   ```bash
   bash setup.sh --chatgpt --tunnel-client /path/to/tunnel-client
   ```

   **Windows**

   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1 -ChatGPT -TunnelClient "C:\path\to\tunnel-client.exe"
   ```

3. Enter the tunnel ID and runtime key when prompted. If your ILIAS account needs setup, the browser form opens. Keep the terminal running.
4. Open [ChatGPT Plugins](https://chatgpt.com/plugins), choose **Add custom MCP server → Tunnel**, and select your tunnel ID. Choose **No authentication** for the MCP server and install it as a personal plugin for your ILIAS account. In a chat, select it using `@` and ask for your courses.

If you installed the wheel, use `ilias-mcp-chatgpt` directly. The launcher
also reads `CONTROL_PLANE_TUNNEL_ID` and `CONTROL_PLANE_API_KEY` when set.
Access depends on your OpenAI account and workspace permissions.
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) · [Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)

## Install from source

You need your **ILIAS login** and **Python 3.10+** or [uv](https://docs.astral.sh/uv/getting-started/installation/).
Download and extract the source archive from [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases)
or clone this repository with Git.

```bash
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
```

From the extracted or cloned directory, run the command for your system.

**macOS and Linux**

```bash
bash setup.sh
```

On Debian and Ubuntu, install `python3-venv` if your Python installation is
missing it. Linux also needs an unlocked Secret Service keyring in the same
user session, such as GNOME Keyring. For Claude on Windows, run the Windows
installer from PowerShell so the MCP server uses Windows Credential Manager.

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The installer opens a local browser page. Enter your ILIAS username and
password, then select **Save account**. Setup checks the login with ILIAS,
stores the password in your system credential store, and adds the server to
Claude Desktop. If the browser does not open, copy the address from the
terminal. If the password is already stored, leave the password field blank.
Rerun the same setup command whenever your password changes.

Quit Claude Desktop completely and reopen it. On Windows, quit from the
system tray. Try asking Claude to list your courses.

> List my courses on ILIAS.

Claude Desktop is available on [macOS, Windows and Linux (beta)](https://support.claude.com/en/articles/10065433-install-claude-desktop).
Use `--terminal` (PowerShell: `-Terminal`) to enter your credentials in the
terminal instead. Use `--skip-check` (PowerShell: `-SkipCheck`) when ILIAS is
temporarily unreachable.

### Other MCP clients

Add `--no-claude` (PowerShell: `-NoClaude`) to save the account and print the
local MCP command without changing Claude settings. An installed wheel exposes
the same setup as `ilias-mcp-config setup`.

In a compatible local MCP client, configure the printed command as a stdio
server.

## How does it work?

The program runs on your computer and retrieves ILIAS pages or files when
your assistant asks for them. It saves previous checks locally so later
scans can report changes. Checks run on request; there are no automatic
background notifications.

**MCP** stands for [Model Context Protocol](https://modelcontextprotocol.io).
It lets compatible AI apps use tools like this one. Manual configuration for
other MCP clients is included below.

## Your account and course data

- Your password is saved in **macOS Keychain**, **Windows Credential Manager**
  or a **Linux Secret Service** keyring. The local setup profile stores your
  username and any custom download folder.
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
| Linux | `${XDG_CONFIG_HOME:-~/.config}/Claude/` |

If you prefer to configure the credentials and client separately, run
`ilias-mcp-config setup --no-claude` from your virtual environment.
The optional `--download-root DIR` (PowerShell: `-DownloadRoot DIR`) sets
where downloaded files can be saved.

For a full diagnostic with your saved account, run `ilias-mcp-check`. It opens
two courses by default and writes `selftest-report.json`. Add `--dump DIR` only
when you need HTML for debugging.

| Variable | Default |
|---|---|
| `ILIAS_USER` | Username saved by setup; this variable overrides it |
| `ILIAS_BASE_URL` | `https://ilias.uni-konstanz.de` |
| `ILIAS_CLIENT_ID` | `ILIASKONSTANZ` |
| `ILIAS_LANG` | `en`; the session UI language follows your ILIAS profile |
| `ILIAS_MIN_INTERVAL` | `1.0` seconds between requests; minimum `0.5` |
| `ILIAS_MAX_REQUESTS_PER_CALL` | `60`; `ilias_scan` uses `120`, `ilias_check_all` `400` |
| `ILIAS_TIMEOUT` | `30.0` seconds |
| `ILIAS_KEYCHAIN_SERVICE` | `ilias-mcp` |
| `ILIAS_CACHE_DIR` | `~/Library/Caches/ilias-mcp` on macOS, `%LOCALAPPDATA%\ilias-mcp\Cache` on Windows, `${XDG_CACHE_HOME:-~/.cache}/ilias-mcp` on Linux |
| `ILIAS_DOWNLOAD_ROOT` | The configured folder, or `ILIAS` inside your system Documents folder |

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
`pages`, `offset` and `version` that continue it. If the file changed in
between, the new version starts again from the beginning of the page. A page
counts as read only once all of it has been returned for one version. “Read” means the text was returned by the tool, not
that the user has read it.

**Change detection.** `ilias_scan` compares one course with its last committed
snapshot, then saves a pending snapshot and returns a `scan_id`. Calling
`ilias_commit_scan` with that ID replaces the course's comparison baseline.
The first scan treats all items as new. When part of a course cannot be
opened, the scan is marked `incomplete`: items it could not reach are listed
as `not_seen` instead of removed, and committing keeps them in the baseline
until a complete scan shows whether they still exist. A scan narrower than
the baseline (smaller `depth`, or without assignments or forums) leaves what it
did not look at unchanged in the baseline. Forum unread counts are excluded
from the comparison. `ilias_check_all` compares news with the last check that
could read the news page, so a check without it does not skip any news.

**Cache.** Reading records, extracted text, snapshots and learned routes are
kept per ILIAS installation and account under `accounts/` in the cache
directory. To import a cache from version 0.2 or older, identify the account
it belongs to with `ilias-mcp-config cache --user firstname.lastname --adopt`.
Clearing the cache resets the saved history.

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
| HTTPS, configured host and port, and known entry points | Restricts destinations, including redirect hops |

The code separates ILIAS access from the MCP interface:

```text
src/ilias_mcp/
  policy.py       Request checks
  client.py       HTTP requests, login, sessions, rate limits, and budgets
  credentials.py  system credential store access
  parsers.py      HTML parsing
  dates.py        German/English dates in Europe/Berlin
  files.py        Text extraction and reading records
  service.py      Course scanning, comparisons, reading, and downloads
  server.py       MCP tools over stdio
  check.py        Live connection self-test
  install.py      account setup and Claude configuration (ilias-mcp-config)
  chatgpt.py      Secure MCP Tunnel launcher (ilias-mcp-chatgpt)
  setup_web.py    local browser form for account setup
tests/           Fake ILIAS server and HTML fixtures
```

To run the development tests:

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

On Windows, use `.venv\Scripts\pip` and `.venv\Scripts\pytest`. If setup used
`uv`, use `uv pip install -e ".[dev]"` to install the test dependencies.

Tests use `httpx.MockTransport` and HTML fixtures. They cover request checks,
login and re-login, redirects, rate limits, parsing, reading records, change
detection, and MCP tool calls.

For live parser debugging, `ilias-mcp-check --dump DIR` saves fetched pages
and attempts to redact action tokens and hidden form values. These pages
and the self-test report can still contain private course information.
Use `.debug/pages` for dumps to keep them out of Git along with the default
`selftest-report.json`.
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


## Versions and releases

Check the installed version with `ilias-mcp --version`. The package, command-line
tools and MCP server share the version in `src/ilias_mcp/__init__.py`.

For maintainers, update that file using [Semantic Versioning](https://semver.org/),
then commit the change and push the matching `vMAJOR.MINOR.PATCH` tag.

```bash
git tag -a v0.4.0 -m "Release 0.4.0"
git push origin v0.4.0
```

The release workflow checks the tag against the package version, runs the test
matrix on Windows, macOS and Linux, then attaches the Claude `.mcpb`, wheel,
and source package to a GitHub Release. Build the bundle locally with
`python scripts/build_mcpb.py`. To upgrade, install the new bundle or update
your source checkout and rerun setup. Your existing password can be reused.
