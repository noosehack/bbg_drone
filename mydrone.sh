#!/usr/bin/env bash
set -euo pipefail

PY_EXE="$(command -v py.exe 2>/dev/null || true)"
[[ -n "$PY_EXE" ]] || { echo "error: py.exe not found in PATH. Is Windows Python installed and WSL PATH integration enabled?" >&2; exit 1; }

DRONE_LINUX="$(dirname "$0")/mydrone.py"
[[ -f "$DRONE_LINUX" ]] || { echo "error: mydrone.py not found: $DRONE_LINUX" >&2; exit 1; }

DRONE_WIN="$(wslpath -w "$DRONE_LINUX")"

exec "$PY_EXE" -3.12 "$DRONE_WIN" "$@"
