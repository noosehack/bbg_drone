#!/usr/bin/env bash
set -euo pipefail



WINUSER="dplst"
PY_WIN_PATH='C:\Users\dplst\AppData\Local\Programs\Python\Launcher\py.exe'

DRONE_LINUX="$(dirname "$0")/mydrone.py"
[[ -f "$DRONE_LINUX" ]] || { echo "mydrone.py not found: $DRONE_LINUX" >&2; exit 1; }
[[ -n "$PY_WIN_PATH" ]] || { echo "PY_WIN_PATH is not set (Windows path to py.exe)." >&2; exit 1; }

win_to_wsl() {
  local p="$1"
  local drive="$(echo "$p" | cut -c1 | tr 'A-Z' 'a-z')"
  local rest="$(echo "$p" | cut -c3- | sed 's#\\#/#g')"
  echo "/mnt/$drive/$rest"
}

PY_EXE="$(win_to_wsl "$PY_WIN_PATH")"
DRONE_WIN="$(wslpath -w "$DRONE_LINUX")"

exec "$PY_EXE" -3.12 "$DRONE_WIN" "$@"
