# ilias-mcp

[English](README.md) · [Türkçe](README.tr.md) · **Deutsch**

**Frag deinen KI-Assistenten nach deinen ILIAS-Kursen.**

Finde Kursmaterialien, prüfe Abgabefristen und sieh nach, was sich seit deinem
letzten gespeicherten Abgleich geändert hat – alles direkt aus dem KI-Chat.

Ein unabhängiges studentisches Projekt für die **Universität Konstanz**. Es
verbindet deinen MCP-Client mit den Kursinhalten, auf die du mit deinem eigenen
ILIAS-Konto zugreifen kannst. Der Zugriff ist rein lesend: Es gibt keine
Werkzeuge, um Aufgaben abzugeben, Nachrichten zu schreiben oder Kursen
beizutreten.

## Was kann ich fragen?

- „Welche Abgaben stehen diese Woche in meinen Kursen an?“
- „Was hat sich in diesem Kurs seit meinem letzten Abgleich geändert?“
- „Finde die neuesten Vorlesungsfolien und fasse sie für mich zusammen.“
- „Zeig mir die Ankündigungen und Forenthemen dieses Kurses.“

Der Assistent ruft die Informationen über ilias-mcp ab und beantwortet damit
deine Frage.

## Anwendungsbeispiele

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

## Installation in Claude Desktop

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

## Verbindung mit ChatGPT

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

## Installation aus dem Quellcode

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

### Andere MCP-Clients

Mit `--no-claude` (PowerShell: `-NoClaude`) wird das Konto gespeichert und der
lokale MCP-Befehl ausgegeben, ohne die Claude-Einstellungen zu ändern. Ein
installiertes Wheel bietet dasselbe Setup als `ilias-mcp-config setup`.

Trage den ausgegebenen Befehl in einem kompatiblen lokalen MCP-Client als
stdio-Server ein.

## Wie funktioniert es?

Das Programm läuft auf deinem Computer und ruft ILIAS-Seiten oder -Dateien ab,
wenn dein Assistent danach fragt. Frühere Abgleiche speichert es lokal, damit
spätere Durchläufe Änderungen melden können. Abgleiche laufen nur auf Anfrage;
es gibt keine automatischen Benachrichtigungen im Hintergrund.

**MCP** steht für [Model Context Protocol](https://modelcontextprotocol.io).
Damit können kompatible KI-Apps Werkzeuge wie dieses nutzen. Die manuelle
Konfiguration für andere MCP-Clients steht im technischen Teil der englischen
README.

## Dein Konto und deine Kursdaten

- Dein Passwort wird im **macOS-Schlüsselbund**, in der
  **Windows-Anmeldeinformationsverwaltung** oder in einem
  **Linux-Secret-Service-Schlüsselbund** gespeichert. Das lokale Setup-Profil enthält deinen
  Benutzernamen und gegebenenfalls einen eigenen Download-Ordner.
- Gespeicherte Abgleiche und aus Dateien gewonnener Text werden auf deinem
  Computer zwischengespeichert.
- Abgerufene Inhalte gehen an deine **KI-Anwendung** und können deren
  Cloud-Modellanbieter erreichen. Die lokale Installation macht die
  KI-Verarbeitung nicht lokal.

## Aktueller Umfang

Eine frühe Version für ILIAS 10 in Konstanz, mit deutscher und englischer
Oberfläche. Andere Installationen brauchen eventuell Anpassungen;
Shibboleth/SSO-Anmeldung wird nicht unterstützt. Text wird aus PDF-,
PowerPoint-, Word- und Textdateien sowie ZIP-Archiven gelesen. Gescannte
Bilder bräuchten OCR, das nicht enthalten ist. Der Forenzugriff umfasst die
Themenlisten.

## Technische Details

Die technische Referenz wird in der englischen README aktuell gehalten:

- [Konfiguration, manuelle Einrichtung und Umgebungsvariablen](README.md#technical-reference)
- [Werkzeugliste, Lesestand, Änderungserkennung und Cache](README.md#technical-reference)
- [Anfrageregeln (nur lesend), Code-Aufbau und Entwicklung](README.md#technical-reference)
- [Versionen und Releases](README.md#versions-and-releases)

## Feedback und Beiträge

Wenn du es ausprobierst, freue ich mich über Rückmeldungen zur Einrichtung, zu
fehlenden Informationen oder zu einem nützlichen Lern-Workflow. Eröffne ein
[Issue](https://github.com/keremilgaz/ilias-mcp/issues) und beschreibe, was du
erwartet hast und was passiert ist. Entferne Kontodaten und private
Kursinhalte aus allem, was du teilst.

Nutze das Werkzeug mit deinem eigenen Konto, beschränke Abgleiche auf deine
Kurse und halte dich an die Regeln deiner Universität zu automatisiertem
Zugriff und zu Kursmaterialien.

## Danksagung und Lizenz

Das Wissen über die Seitenstruktur (Selektoren) stammt aus
[PFERD](https://github.com/Garmelon/PFERD) und
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp).

Lizenziert unter [MIT](LICENSE).
