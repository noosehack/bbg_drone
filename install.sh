#!/usr/bin/env bash
set -euo pipefail

OK="[ ok ]"
WARN="[warn]"
FAIL="[fail]"

echo "bbg_drone installer"
echo "-------------------"

# 1. WSL check
if ! grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
    echo "$FAIL This script must run inside WSL."
    exit 1
fi
echo "$OK Running in WSL."

# 2. Find py.exe
PY_EXE="$(command -v py.exe 2>/dev/null || true)"
if [[ -z "$PY_EXE" ]]; then
    echo "$FAIL py.exe not found in PATH."
    echo "      Make sure Windows Python is installed and WSL PATH integration is enabled."
    echo "      See: https://learn.microsoft.com/en-us/windows/python/beginners"
    exit 1
fi
echo "$OK Found py.exe: $PY_EXE"

# 3. Check Python 3.12 is available
if ! "$PY_EXE" -3.12 --version &>/dev/null; then
    echo "$FAIL Python 3.12 not found via py.exe."
    echo "      Install it from https://www.python.org/downloads/ and rerun."
    exit 1
fi
PY_VER="$("$PY_EXE" -3.12 --version 2>&1)"
echo "$OK $PY_VER available."

# 4. Check argcomplete
if ! "$PY_EXE" -3.12 -c "import argcomplete" &>/dev/null; then
    echo "      Installing argcomplete..."
    "$PY_EXE" -3.12 -m pip install --quiet argcomplete
    echo "$OK argcomplete installed."
else
    echo "$OK argcomplete already installed."
fi

# 5. Check blpapi (warn only — requires Bloomberg terminal)
if ! "$PY_EXE" -3.12 -c "import blpapi" &>/dev/null; then
    echo "$WARN blpapi not found. mydrone will not run without it."
    echo "      Install it with: py -3.12 -m pip install blpapi"
    echo "      Requires an active Bloomberg terminal connection."
else
    echo "$OK blpapi available."
fi

# 6. Make scripts executable
chmod +x "$(dirname "$0")/mydrone.sh"
chmod +x "$(dirname "$0")/mydrone.py"
echo "$OK Scripts are executable."

echo ""
echo "Setup complete. Usage:"
echo "  ./mydrone.sh histo eod -i \"ES1 Index\" -f PX_LAST"
echo "  ./mydrone.sh --help"
