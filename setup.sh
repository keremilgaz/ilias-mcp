#!/usr/bin/env bash
# Install ilias-mcp on macOS or Linux and open account setup.
set -euo pipefail
cd "$(dirname "$0")"

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo "On Windows, run setup.ps1 in PowerShell." >&2; exit 1 ;;
esac

if [[ ! -x .venv/bin/python ]]; then
  if [[ -e .venv ]]; then
    echo "The existing .venv is incompatible with this system. Rename it and rerun setup." >&2
    exit 1
  fi
  if command -v uv >/dev/null 2>&1; then
    uv venv --python '>=3.10' .venv
  else
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
      if command -v "$candidate" >/dev/null 2>&1 &&
         "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        python="$candidate"
        break
      fi
    done
    if [[ -z "${python:-}" ]]; then
      echo "Install Python 3.10+ or uv, then rerun setup." >&2
      exit 1
    fi
    if ! "$python" -m venv .venv; then
      echo "Install your Python's venv package (e.g. python3-venv on Debian/Ubuntu), or use uv." >&2
      exit 1
    fi
  fi
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -e .
else
  if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m ensurepip --upgrade >/dev/null
  fi
  .venv/bin/python -m pip install -e .
fi

if [[ "${1:-}" == "--chatgpt" ]]; then
  shift
  exec .venv/bin/python -m ilias_mcp.chatgpt "$@"
fi
exec .venv/bin/python -m ilias_mcp.install setup "$@"
