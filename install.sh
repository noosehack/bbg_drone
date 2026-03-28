#!/usr/bin/env bash
set -euo pipefail

OK="[ ok ]"
WARN="[warn]"
FAIL="[fail]"

FULL=false
[[ "${1:-}" == "--full" ]] && FULL=true

REPO_DIR="$(dirname "$0")"

echo "bbg_drone installer"
echo "-------------------"
$FULL && echo "mode: full" || echo "mode: minimal"
echo ""

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
    exit 1
fi
echo "$OK Found py.exe: $PY_EXE"

# 3. Check Python 3.12
if ! "$PY_EXE" -3.12 --version &>/dev/null; then
    echo "$FAIL Python 3.12 not found via py.exe."
    echo "      Install it from https://www.python.org/downloads/ and rerun."
    exit 1
fi
PY_VER="$("$PY_EXE" -3.12 --version 2>&1)"
echo "$OK $PY_VER available."

# 4. argcomplete
if ! "$PY_EXE" -3.12 -c "import argcomplete" &>/dev/null; then
    echo "      Installing argcomplete..."
    "$PY_EXE" -3.12 -m pip install --quiet argcomplete
    echo "$OK argcomplete installed."
else
    echo "$OK argcomplete already installed."
fi

# 5. blpapi (warn only)
if ! "$PY_EXE" -3.12 -c "import blpapi" &>/dev/null; then
    echo "$WARN blpapi not found. mydrone will not run without it."
    echo "      Install it with: py -3.12 -m pip install blpapi"
    echo "      Requires an active Bloomberg terminal connection."
else
    echo "$OK blpapi available."
fi

# 6. Make core scripts executable
chmod +x "$REPO_DIR/mydrone.sh" "$REPO_DIR/mydrone.py"
echo "$OK Core scripts are executable."

# ── FULL MODE ─────────────────────────────────────────────────────────────────
if $FULL; then
    echo ""
    echo "── full install ──"

    # 7. dos2unix
    if command -v dos2unix &>/dev/null; then
        echo "$OK dos2unix already installed."
    else
        echo "      Installing dos2unix..."
        sudo apt-get install -y -q dos2unix
        echo "$OK dos2unix installed."
    fi

    # 8. blawkops_sh submodule
    if [[ ! -f "$REPO_DIR/blawkops_sh/blawkops.sh" ]]; then
        echo "      Initialising blawkops_sh submodule..."
        git -C "$REPO_DIR" submodule update --init --recursive
        echo "$OK blawkops_sh ready."
    else
        echo "$OK blawkops_sh already present."
    fi

    # 9. get_BBG scripts
    for script in get_BBG.sh get_BBG_ECO.sh; do
        if [[ -f "$REPO_DIR/$script" ]]; then
            chmod +x "$REPO_DIR/$script"
            echo "$OK $script is executable."
        else
            echo "$WARN $script not found — coming soon."
        fi
    done

    # 10. Universe files
    all_unis=true
    for uni in UNI_FUT.csv UNI_ETF_AZ.csv UNI_CTY_YC2Y10.csv ECO.csv; do
        if [[ ! -f "$REPO_DIR/$uni" ]]; then
            echo "$WARN $uni missing."
            all_unis=false
        fi
    done
    $all_unis && echo "$OK All universe files present."

fi

# ── DONE ──────────────────────────────────────────────────────────────────────
echo ""
echo "Setup complete. Usage:"
echo "  ./mydrone.sh histo eod -i \"ES1 Index\" -f PX_LAST"
echo "  ./mydrone.sh --help"
$FULL && echo "  ./get_BBG.sh [--upload]"
