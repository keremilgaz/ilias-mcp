# ilias-mcp

**English** · [Türkçe](#türkçe) · [Deutsch](#deutsch)

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

---

## Türkçe

[English](#ilias-mcp) · **Türkçe** · [Deutsch](#deutsch)

**ILIAS derslerini yapay zekâ asistanına sor.**

Ders materyallerini bul, ödev son tarihlerini kontrol et ve son kayıtlı
kontrolünden bu yana nelerin değiştiğini gör; hepsini yapay zekâ sohbetinden.

**Konstanz Üniversitesi** için bağımsız bir öğrenci projesi. MCP istemcini,
kendi ILIAS hesabınla erişebildiğin ders içeriğine bağlar. Erişim yalnızca
okuma amaçlıdır: ödev teslim etmek, mesaj yazmak ya da derse kaydolmak için
hiçbir araç yoktur.

### Neler sorabilirim?

- “Bu hafta hangi derslerimde ödev teslimi var?”
- “Son kontrolümden bu yana bu derste neler değişti?”
- “En son ders slaytlarını bul ve benim için özetle.”
- “Bu dersin duyurularını ve forum başlıklarını göster.”

Asistan bilgileri ilias-mcp üzerinden alır ve sorunu yanıtlamak için kullanır.

### Kullanım senaryoları

**Haftalık kontrol.** Haftada bir şunu sor:

> Bu dönemki tüm ILIAS derslerimi kontrol et ve son kontrolümden bu yana neyin yeni olduğunu söyle.

Asistan bu dönemin bütün derslerini tek seferde kontrol eder. Yalnızca yeni ya
da değişmiş dosyaları, ödevleri, forum başlıklarını ve duyuruları, ayrıca
önümüzdeki 14 gün içindeki son tarihleri raporlar. Önemli olanları not
ettikten sonra kontrolü kaydeder; gelecek haftaki kontrol oradan başlar. İlk
kontrol her şeyi yeni olarak listeler.

**Son tarihlere toplu bakış.**

> Açık bütün ödevleri son tarihleriyle birlikte, tarihe göre sıralı listele ve bu hafta teslim edilecekleri işaretle.

Derslerindeki ödev sayfalarını okur: son tarihler, başlangıç tarihleri ve bir
şey teslim edip etmediğin. Asistanın bir takvim ya da yapılacaklar uygulamasına
da bağlıysa tarihleri oraya aktarabilir.

**Derse hazırlık.**

> Bir sonraki İstatistik dersinin slaytlarını bul, özetle ve sorabileceğim üç soru öner.

Dersteki en yeni dosyayı bulur ve metniyle çalışır. Okunan sayfalar hatırlanır;
sonraki bir istekte yalnızca yeni olan kısım gelir.

**Sadece PDF'lerde yazan görevler.** Bazı talimatlar yalnızca slaytlarda ya da
dağıtılan belgelerde yer alır:

> Bu dönemki ders PDF'lerinde teslim, son tarih ya da sunum geçen yerleri ara ve bulduklarını listele.

Anahtar kelime araması, belgelerin tamamı yerine eşleşen bölümleri sayfa
numaralarıyla döndürür.

**Ara verdikten sonra yetişmek.**

> Seminerin iki haftasını kaçırdım. Derste neler değişti, duyurularda ne yazıyordu?

Dersi son kayıtlı kontrolünle karşılaştırır, yeni materyalleri ve duyuruları
gösterir, aktif forum başlıklarını listeler. Başlıklar açılmaz, bu yüzden
hiçbir şey okunmuş olarak işaretlenmez.

**Materyalleri klasörüne kaydetmek.**

> Bu dersin yeni slaytlarını ILIAS klasörümde "İstatistik" altına indir.

Dosyalar yalnızca ayarlanan indirme klasörünün içine kaydedilir; aynı adı
taşıyan farklı bir dosyanın üzerine asla yazılmaz.

**Sınav hazırlığı.**

> Bu dersin bütün ders slaytlarını gözden geçir ve her konunun geçtiği slaytlarla birlikte bir konu listesi çıkar.

Dosyalar sırayla, uzun olanlar parça parça okunur. Okuma kaydı nelerin
tamamlandığını sohbetler arasında da takip eder.

Yapmadıkları: ödev teslim etmek, forumlara yazmak, derslere kaydolmak ya da
forum başlıklarını açmak.

### Claude Desktop'a kurulum

1. [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) sayfasından `ilias-mcp-<sürüm>.mcpb` dosyasını indir.
2. Claude Desktop'ta **Settings → Desktop app → Manage Extensions → Advanced settings → Install Extension** yolunu izleyip paketi seç.
3. Bir Claude sohbetinde **Open ILIAS setup** de. Açılan yerel tarayıcı formuna giriş bilgilerini gir, sonra Claude'dan derslerini listelemesini iste.

Python'u ve bağımlılıkları Claude Desktop ilk açılışta kendisi yönetir. Hesabını
daha önce kurulum betiğiyle kaydettiysen derslerini hemen sorabilirsin. Elle
kurulumdan geçiyorsan, tek bir araç seti görmek için Claude Desktop'taki eski
ILIAS girdisini devre dışı bırak.
[Claude Desktop eklenti talimatları](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

Linux'ta aynı kullanıcı oturumunda kilidi açık bir Secret Service anahtarlığı
olmalı. Daha önce kullandığın hesabı ya da şifreyi değiştirdikten sonra Claude
Desktop'u yeniden başlat.

### ChatGPT'ye bağlama

1. [OpenAI Platform](https://platform.openai.com/settings/organization/tunnels) üzerinde bir tünel oluştur ya da mevcut olanı bul, ChatGPT çalışma alanınla ilişkilendir ve **Tunnels Read + Use** yetkili bir çalışma zamanı (runtime) API anahtarı oluştur. Sistemine uygun [resmî tunnel-client](https://github.com/openai/tunnel-client/releases/latest) dosyasını indirip arşivden çıkar.
2. Çıkardığın ILIAS kaynak arşivinin ya da deponun klasöründe, sistemine uygun komutu çalıştır. `tunnel-client` `PATH` içindeyse çalıştırılabilir dosya yolunu yazmana gerek yok.

   **macOS ve Linux**

   ```bash
   bash setup.sh --chatgpt --tunnel-client /path/to/tunnel-client
   ```

   **Windows**

   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1 -ChatGPT -TunnelClient "C:\path\to\tunnel-client.exe"
   ```

3. İstendiğinde tünel kimliğini ve runtime anahtarını gir. ILIAS hesabının kurulması gerekiyorsa tarayıcı formu açılır. Terminali açık bırak.
4. [ChatGPT Plugins](https://chatgpt.com/plugins) sayfasında **Add custom MCP server → Tunnel**'ı seç ve tünel kimliğini seç. MCP sunucusu için **No authentication**'ı seç ve onu ILIAS hesabın için kişisel bir eklenti olarak kur. Bir sohbette `@` ile seç ve derslerini sor.

Wheel paketini kurduysan doğrudan `ilias-mcp-chatgpt` komutunu kullan. Başlatıcı
tanımlıysa `CONTROL_PLANE_TUNNEL_ID` ve `CONTROL_PLANE_API_KEY` değişkenlerini de
okur. Erişim, OpenAI hesabının ve çalışma alanının izinlerine bağlıdır.
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) · [Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)

### Kaynaktan kurulum

**ILIAS giriş bilgilerine** ve **Python 3.10+** ya da [uv](https://docs.astral.sh/uv/getting-started/installation/) aracına ihtiyacın var.
Kaynak arşivini [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) sayfasından indirip çıkar
ya da bu depoyu Git ile klonla.

```bash
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
```

Çıkardığın ya da klonladığın klasörde, sistemine uygun komutu çalıştır.

**macOS ve Linux**

```bash
bash setup.sh
```

Debian ve Ubuntu'da Python kurulumunda eksikse `python3-venv` paketini kur.
Linux'ta ayrıca aynı kullanıcı oturumunda kilidi açık bir Secret Service
anahtarlığı (örneğin GNOME Keyring) gerekir. Windows'taki Claude için Windows
kurulum betiğini PowerShell'den çalıştır; böylece MCP sunucusu Windows Kimlik
Bilgileri Yöneticisi'ni (Credential Manager) kullanır.

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Kurulum betiği yerel bir tarayıcı sayfası açar. ILIAS kullanıcı adını ve
şifreni girip **Save account**'a bas. Kurulum girişi ILIAS'ta doğrular, şifreyi
sistemin kimlik bilgisi deposuna kaydeder ve sunucuyu Claude Desktop'a ekler.
Tarayıcı açılmazsa adresi terminalden kopyala. Şifre zaten kayıtlıysa şifre
alanını boş bırak. Şifren değiştiğinde aynı kurulum komutunu yeniden çalıştır.

Claude Desktop'u tamamen kapatıp yeniden aç. Windows'ta sistem tepsisinden
çık. Ardından Claude'dan derslerini listelemesini iste.

> ILIAS'taki derslerimi listele.

Claude Desktop [macOS, Windows ve Linux (beta)](https://support.claude.com/en/articles/10065433-install-claude-desktop) için mevcut.
Giriş bilgilerini tarayıcı yerine terminalde girmek için `--terminal`
(PowerShell: `-Terminal`) kullan. ILIAS geçici olarak erişilemiyorsa
`--skip-check` (PowerShell: `-SkipCheck`) kullan.

#### Diğer MCP istemcileri

Claude ayarlarını değiştirmeden hesabı kaydetmek ve yerel MCP komutunu
yazdırmak için `--no-claude` (PowerShell: `-NoClaude`) ekle. Kurulu bir wheel
paketinde aynı kurulum `ilias-mcp-config setup` olarak bulunur.

Uyumlu bir yerel MCP istemcisinde, yazdırılan komutu stdio sunucusu olarak
ayarla.

### Nasıl çalışır?

Program senin bilgisayarında çalışır ve asistanın istediğinde ILIAS
sayfalarını ya da dosyalarını alır. Önceki kontrolleri yerel olarak kaydeder;
böylece sonraki taramalar değişiklikleri raporlayabilir. Kontroller yalnızca
istek üzerine çalışır; arka planda otomatik bildirim yoktur.

**MCP**, [Model Context Protocol](https://modelcontextprotocol.io)'ün
kısaltmasıdır. Uyumlu yapay zekâ uygulamalarının bunun gibi araçları
kullanmasını sağlar. Diğer MCP istemcileri için elle yapılandırma, İngilizce
README'nin teknik bölümünde anlatılıyor.

### Hesabın ve ders verilerin

- Şifren **macOS Anahtar Zinciri**'nde, **Windows Kimlik Bilgileri
  Yöneticisi**'nde ya da bir **Linux Secret Service** anahtarlığında saklanır.
  Yerel kurulum profili yalnızca kullanıcı adını ve varsa özel indirme
  klasörünü tutar.
- Kaydedilen kontroller ve dosyalardan çıkarılan metinler bilgisayarında
  önbelleğe alınır.
- Alınan içerik **yapay zekâ uygulamanla** paylaşılır ve onun bulut model
  sağlayıcısına ulaşabilir. Yerel kurulum, yapay zekâ işlemesini yerel yapmaz.

### Mevcut kapsam

Konstanz'ın ILIAS 10 sürümü için erken bir sürüm; Almanca ve İngilizce arayüzü
destekler. Başka kurulumlar uyarlama gerektirebilir; Shibboleth/SSO girişi
desteklenmez. PDF, PowerPoint, Word, metin dosyaları ve ZIP arşivlerinden metin
okur. Taranmış görüntüler OCR gerektirir; OCR dahil değildir. Forum erişimi
başlık listeleriyle sınırlıdır.

### Teknik ayrıntılar

Teknik başvuru bölümleri İngilizce README'de güncel tutuluyor:

- [Yapılandırma ve elle kurulum, ortam değişkenleri](#technical-reference)
- [Araçların listesi, okuma kayıtları, değişiklik takibi ve önbellek](#technical-reference)
- [İstek politikası (salt okuma kuralları), kod yapısı ve geliştirme](#technical-reference)
- [Sürümler ve yayınlar](#versions-and-releases)

### Geri bildirim ve katkı

Denediysen kurulum, eksik bilgiler ya da işe yarayan bir çalışma akışı
hakkındaki geri bildirimlerin memnuniyetle karşılanır. Ne beklediğini ve ne
olduğunu yazarak bir [issue](https://github.com/keremilgaz/ilias-mcp/issues)
aç. Paylaştığın her şeyden hesap bilgilerini ve kişisel ders içeriğini çıkar.

Aracı kendi hesabınla kullan, taramaları kendi derslerinle sınırlı tut ve
üniversitenin otomatik erişim ile ders materyallerine ilişkin kurallarına uy.

### Teşekkür ve lisans

Seçici (selector) bilgileri [PFERD](https://github.com/Garmelon/PFERD) ve
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp)
projelerinden gelir.

[MIT](LICENSE) lisansı ile lisanslanmıştır.

---

## Deutsch

[English](#ilias-mcp) · [Türkçe](#türkçe) · **Deutsch**

**Frag deinen KI-Assistenten nach deinen ILIAS-Kursen.**

Finde Kursmaterialien, prüfe Abgabefristen und sieh nach, was sich seit deinem
letzten gespeicherten Abgleich geändert hat – alles direkt aus dem KI-Chat.

Ein unabhängiges studentisches Projekt für die **Universität Konstanz**. Es
verbindet deinen MCP-Client mit den Kursinhalten, auf die du mit deinem eigenen
ILIAS-Konto zugreifen kannst. Der Zugriff ist rein lesend: Es gibt keine
Werkzeuge, um Aufgaben abzugeben, Nachrichten zu schreiben oder Kursen
beizutreten.

### Was kann ich fragen?

- „Welche Abgaben stehen diese Woche in meinen Kursen an?“
- „Was hat sich in diesem Kurs seit meinem letzten Abgleich geändert?“
- „Finde die neuesten Vorlesungsfolien und fasse sie für mich zusammen.“
- „Zeig mir die Ankündigungen und Forenthemen dieses Kurses.“

Der Assistent ruft die Informationen über ilias-mcp ab und beantwortet damit
deine Frage.

### Anwendungsbeispiele

**Wöchentlicher Überblick.** Frag einmal pro Woche:

> Prüfe alle meine ILIAS-Kurse dieses Semesters und sag mir, was seit meinem letzten Abgleich neu ist.

Der Assistent prüft alle Kurse des aktuellen Semesters in einem Durchgang. Er
meldet nur neue oder geänderte Dateien, Aufgaben, Forenthemen und
Ankündigungen sowie Fristen in den nächsten 14 Tagen. Wenn du das Wichtige
notiert hast, speichert er den Abgleich; der Abgleich nächste Woche setzt dort
an. Der allererste Abgleich listet alles als neu auf.

**Fristen auf einen Blick.**

> Liste alle offenen Aufgaben mit ihren Fristen nach Datum sortiert auf und markiere die, die diese Woche fällig sind.

Er liest die Übungsseiten deiner Kurse: Fristen, Startdaten und ob du schon
etwas abgegeben hast. Ist dein Assistent zusätzlich mit einem Kalender oder
einer To-do-App verbunden, kann er die Termine dorthin übernehmen.

**Vorbereitung auf eine Vorlesung.**

> Finde die Folien für die nächste Statistik-Vorlesung, fasse sie zusammen und schlag drei Fragen vor, die ich stellen könnte.

Er findet die neueste Datei im Kurs und arbeitet mit ihrem Text. Bereits
gelesene Seiten werden gemerkt, sodass eine spätere Anfrage nur Neues liefert.

**Aufgaben, die nur in PDFs stehen.** Manche Hinweise stehen nur in Folien oder
Handouts:

> Durchsuche die Kurs-PDFs dieses Semesters nach Abgabe, Frist oder Präsentation und liste auf, was du findest.

Eine Stichwortsuche liefert die passenden Stellen mit Seitenzahlen statt
ganzer Dokumente.

**Nach einer Pause aufholen.**

> Ich habe zwei Wochen im Seminar verpasst. Was hat sich im Kurs geändert, und was stand in den Ankündigungen?

Er vergleicht den Kurs mit deinem letzten gespeicherten Abgleich, zeigt neue
Materialien und Ankündigungen und listet aktive Forenthemen auf. Die Beiträge
werden nicht geöffnet, daher wird nichts als gelesen markiert.

**Materialien in deinem Ordner speichern.**

> Lade die neuen Folien dieses Kurses in meinen ILIAS-Ordner unter „Statistik“ herunter.

Dateien werden nur innerhalb deines eingestellten Download-Ordners gespeichert;
eine andere Datei mit demselben Namen wird nie überschrieben.

**Prüfungsvorbereitung.**

> Geh alle Vorlesungsfolien dieses Kurses durch und erstelle eine Themenliste mit den Folien, auf denen jedes Thema vorkommt.

Die Dateien werden nacheinander gelesen, lange in Teilen. Der Lesestand hält
fest, was schon behandelt wurde – auch über mehrere Unterhaltungen hinweg.

Was es nicht tut: Aufgaben abgeben, in Foren schreiben, sich für Kurse
anmelden oder Forenbeiträge öffnen.

### Installation in Claude Desktop

1. Lade `ilias-mcp-<version>.mcpb` von [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) herunter.
2. Wähle in Claude Desktop **Settings → Desktop app → Manage Extensions → Advanced settings → Install Extension** und dann das Paket.
3. Sag in einem Claude-Chat **Open ILIAS setup**. Gib deine Zugangsdaten im lokalen Browserformular ein und bitte Claude dann, deine Kurse aufzulisten.

Python und die Abhängigkeiten verwaltet Claude Desktop beim ersten Start
selbst. Hast du dein Konto schon mit dem Setup-Skript gespeichert, kannst du
direkt nach deinen Kursen fragen. Wenn du von einer manuellen Installation
wechselst, deaktiviere den alten ILIAS-Eintrag in Claude Desktop, damit du nur
einen Satz Werkzeuge siehst.
[Anleitung zu Claude-Desktop-Erweiterungen](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

Unter Linux muss in derselben Benutzersitzung ein entsperrter
Secret-Service-Schlüsselbund laufen. Nachdem du ein bereits verwendetes Konto oder Passwort
geändert hast, starte Claude Desktop neu.

### Verbindung mit ChatGPT

1. Lege in der [OpenAI Platform](https://platform.openai.com/settings/organization/tunnels) einen Tunnel an oder suche einen vorhandenen heraus, verknüpfe ihn mit deinem ChatGPT-Workspace und erstelle einen Runtime-API-Schlüssel mit **Tunnels Read + Use**. Lade den [offiziellen tunnel-client](https://github.com/openai/tunnel-client/releases/latest) für dein System herunter und entpacke ihn.
2. Führe im entpackten ILIAS-Quellarchiv oder im Repository den Befehl für dein System aus. Liegt `tunnel-client` in deinem `PATH`, lass den Pfad zur ausführbaren Datei weg.

   **macOS und Linux**

   ```bash
   bash setup.sh --chatgpt --tunnel-client /path/to/tunnel-client
   ```

   **Windows**

   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1 -ChatGPT -TunnelClient "C:\path\to\tunnel-client.exe"
   ```

3. Gib auf Nachfrage die Tunnel-ID und den Runtime-Schlüssel ein. Muss dein ILIAS-Konto noch eingerichtet werden, öffnet sich das Browserformular. Lass das Terminal geöffnet.
4. Öffne [ChatGPT Plugins](https://chatgpt.com/plugins), wähle **Add custom MCP server → Tunnel** und dann deine Tunnel-ID. Wähle für den MCP-Server **No authentication** und installiere ihn als persönliches Plugin für dein ILIAS-Konto. Wähle es in einem Chat mit `@` aus und frag nach deinen Kursen.

Hast du das Wheel installiert, nutze direkt `ilias-mcp-chatgpt`. Der Starter
liest außerdem `CONTROL_PLANE_TUNNEL_ID` und `CONTROL_PLANE_API_KEY`, wenn sie
gesetzt sind. Der Zugriff hängt von den Berechtigungen deines OpenAI-Kontos und
Workspaces ab.
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) · [Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)

### Installation aus dem Quellcode

Du brauchst deine **ILIAS-Zugangsdaten** und **Python 3.10+** oder [uv](https://docs.astral.sh/uv/getting-started/installation/).
Lade das Quellarchiv von [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) herunter und entpacke es,
oder klone dieses Repository mit Git.

```bash
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
```

Führe im entpackten oder geklonten Ordner den Befehl für dein System aus.

**macOS und Linux**

```bash
bash setup.sh
```

Unter Debian und Ubuntu installiere `python3-venv`, falls es deiner
Python-Installation fehlt. Linux braucht außerdem in derselben Benutzersitzung
einen entsperrten Secret-Service-Schlüsselbund, etwa GNOME Keyring. Für Claude
unter Windows führe das Windows-Setup in PowerShell aus, damit der MCP-Server
die Windows-Anmeldeinformationsverwaltung (Credential Manager) nutzt.

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Das Setup öffnet eine lokale Browserseite. Gib deinen ILIAS-Benutzernamen und
dein Passwort ein und wähle **Save account**. Das Setup prüft die Anmeldung bei
ILIAS, speichert das Passwort im Anmeldedatenspeicher deines Systems und fügt
den Server zu Claude Desktop hinzu. Öffnet sich der Browser nicht, kopiere die
Adresse aus dem Terminal. Ist das Passwort schon gespeichert, lass das
Passwortfeld leer. Ändert sich dein Passwort, führe denselben Setup-Befehl
erneut aus.

Beende Claude Desktop vollständig und öffne es wieder. Unter Windows beendest
du es über den Infobereich der Taskleiste. Bitte Claude dann, deine Kurse
aufzulisten.

> Liste meine Kurse in ILIAS auf.

Claude Desktop gibt es für [macOS, Windows und Linux (Beta)](https://support.claude.com/en/articles/10065433-install-claude-desktop).
Mit `--terminal` (PowerShell: `-Terminal`) gibst du die Zugangsdaten im
Terminal statt im Browser ein. Mit `--skip-check` (PowerShell: `-SkipCheck`)
überspringst du den Anmeldetest, wenn ILIAS vorübergehend nicht erreichbar
ist.

#### Andere MCP-Clients

Mit `--no-claude` (PowerShell: `-NoClaude`) wird das Konto gespeichert und der
lokale MCP-Befehl ausgegeben, ohne die Claude-Einstellungen zu ändern. Ein
installiertes Wheel bietet dasselbe Setup als `ilias-mcp-config setup`.

Trage den ausgegebenen Befehl in einem kompatiblen lokalen MCP-Client als
stdio-Server ein.

### Wie funktioniert es?

Das Programm läuft auf deinem Computer und ruft ILIAS-Seiten oder -Dateien ab,
wenn dein Assistent danach fragt. Frühere Abgleiche speichert es lokal, damit
spätere Durchläufe Änderungen melden können. Abgleiche laufen nur auf Anfrage;
es gibt keine automatischen Benachrichtigungen im Hintergrund.

**MCP** steht für [Model Context Protocol](https://modelcontextprotocol.io).
Damit können kompatible KI-Apps Werkzeuge wie dieses nutzen. Die manuelle
Konfiguration für andere MCP-Clients steht im technischen Teil der englischen
README.

### Dein Konto und deine Kursdaten

- Dein Passwort wird im **macOS-Schlüsselbund**, in der
  **Windows-Anmeldeinformationsverwaltung** oder in einem
  **Linux-Secret-Service-Schlüsselbund** gespeichert. Das lokale Setup-Profil enthält deinen
  Benutzernamen und gegebenenfalls einen eigenen Download-Ordner.
- Gespeicherte Abgleiche und aus Dateien gewonnener Text werden auf deinem
  Computer zwischengespeichert.
- Abgerufene Inhalte gehen an deine **KI-Anwendung** und können deren
  Cloud-Modellanbieter erreichen. Die lokale Installation macht die
  KI-Verarbeitung nicht lokal.

### Aktueller Umfang

Eine frühe Version für ILIAS 10 in Konstanz, mit deutscher und englischer
Oberfläche. Andere Installationen brauchen eventuell Anpassungen;
Shibboleth/SSO-Anmeldung wird nicht unterstützt. Text wird aus PDF-,
PowerPoint-, Word- und Textdateien sowie ZIP-Archiven gelesen. Gescannte
Bilder bräuchten OCR, das nicht enthalten ist. Der Forenzugriff umfasst die
Themenlisten.

### Technische Details

Die technische Referenz wird in der englischen README aktuell gehalten:

- [Konfiguration, manuelle Einrichtung und Umgebungsvariablen](#technical-reference)
- [Werkzeugliste, Lesestand, Änderungserkennung und Cache](#technical-reference)
- [Anfrageregeln (nur lesend), Code-Aufbau und Entwicklung](#technical-reference)
- [Versionen und Releases](#versions-and-releases)

### Feedback und Beiträge

Wenn du es ausprobierst, freue ich mich über Rückmeldungen zur Einrichtung, zu
fehlenden Informationen oder zu einem nützlichen Lern-Workflow. Eröffne ein
[Issue](https://github.com/keremilgaz/ilias-mcp/issues) und beschreibe, was du
erwartet hast und was passiert ist. Entferne Kontodaten und private
Kursinhalte aus allem, was du teilst.

Nutze das Werkzeug mit deinem eigenen Konto, beschränke Abgleiche auf deine
Kurse und halte dich an die Regeln deiner Universität zu automatisiertem
Zugriff und zu Kursmaterialien.

### Danksagung und Lizenz

Das Wissen über die Seitenstruktur (Selektoren) stammt aus
[PFERD](https://github.com/Garmelon/PFERD) und
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp).

Lizenziert unter [MIT](LICENSE).
