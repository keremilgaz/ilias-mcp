#!/bin/bash
# Set up ilias-mcp on macOS: virtualenv, Keychain password, self-test and
# Claude desktop configuration.
#
#   bash setup.sh               full setup
#   bash setup.sh --skip-check  skip the live self-test (e.g. when only changing the config)
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname)" != "Darwin" ]; then
  echo "setup.sh is for macOS. On Windows, run setup.ps1; elsewhere, see 'Manual setup' in the README."
  exit 1
fi
SERVICE="ilias-mcp"
SKIP_CHECK=0
[ "${1:-}" = "--skip-check" ] && SKIP_CHECK=1

find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 "$HOME/.homebrew/bin/python3" python3; do
    if command -v "$c" >/dev/null 2>&1 &&
       "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      command -v "$c"
      return 0
    fi
  done
  return 1
}

echo "== 1/4 Python environment (.venv)"
if PY="$(find_python)"; then
  echo "   $("$PY" --version) - $PY"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -e .
elif command -v uv >/dev/null 2>&1; then
  uv venv -q -p 3.12 .venv
  uv pip install -q -p .venv/bin/python -e .
else
  echo "   Python 3.10+ not found. Install it (e.g. 'brew install python@3.12') and run this script again."
  exit 1
fi

echo
echo "== 2/4 ILIAS username and password (Keychain)"
read -r -p "   ILIAS username (firstname.lastname): " ILIAS_USER
if [ -z "$ILIAS_USER" ]; then echo "   The username cannot be empty."; exit 1; fi
if security find-generic-password -s "$SERVICE" -a "$ILIAS_USER" >/dev/null 2>&1; then
  echo "   A Keychain item already exists."
  echo "   (To replace it: security delete-generic-password -s $SERVICE -a $ILIAS_USER, then run this script again.)"
else
  echo "   macOS will now ask for your ILIAS password twice. Nothing is shown while you type;"
  echo "   the password goes straight into the Keychain and is never written to a file."
  security add-generic-password -s "$SERVICE" -a "$ILIAS_USER" -l "ILIAS (ilias-mcp)" -w
fi
# A cache from version 0.2 or older records no account: asks whether it is this one's.
.venv/bin/ilias-mcp-config cache --user "$ILIAS_USER" --ask || true

echo
if [ "$SKIP_CHECK" -eq 1 ]; then
  echo "== 3/4 Self-test skipped"
else
  echo "== 3/4 Self-test (log in + 2 courses; roughly 20-45 requests, at most one per second)"
  if ILIAS_USER="$ILIAS_USER" .venv/bin/ilias-mcp-check --report selftest-report.json --dump .debug/pages; then
    echo "   Self-test passed."
  else
    echo "   Part of the self-test failed; see selftest-report.json."
    echo "   (A rejected password is not retried: fix the Keychain item and run this script again.)"
  fi
fi

echo
echo "== 4/4 Claude desktop app"
DEFAULT_ROOT="$HOME/Documents/ILIAS"
read -r -p "   Folder that ilias_download_file may write to [$DEFAULT_ROOT]: " DOWNLOAD_ROOT
DOWNLOAD_ROOT="${DOWNLOAD_ROOT:-$DEFAULT_ROOT}"
read -r -p "   Add the 'ilias' server to the Claude configuration? (a backup is made first) [y/N] " ANSWER
if [[ "$ANSWER" =~ ^[yYeE] ]]; then
  .venv/bin/ilias-mcp-config add --user "$ILIAS_USER" --download-root "$DOWNLOAD_ROOT"
  echo "   Quit the Claude app completely (Cmd+Q) and open it again."
else
  .venv/bin/ilias-mcp-config add --user "$ILIAS_USER" --download-root "$DOWNLOAD_ROOT" --dry-run
fi
