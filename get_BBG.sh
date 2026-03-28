#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(dirname "$0")"
source "$REPO_DIR/blawkops_sh/blawkops.sh"

# Usage: get_BBG.sh [--upload]
#   --upload   also push each file to the remote server after download

UPLOAD=false
[ "${1:-}" = "--upload" ] && UPLOAD=true

MYDRONE="$REPO_DIR/mydrone.sh"

CYAN="\033[1;36m"
GREEN="\033[1;32m"
RESET="\033[0m"

upload() {
    if $UPLOAD; then
        echo -e "    ${GREEN}↑ uploading $1 ...${RESET}"
        bash "$REPO_DIR/scpaws-eu_upload.sh" "$1"
    fi
}

fetch_uni() {
    local uni=$1 out=$2 extra=${3:-}
    local tickers
    tickers=$(paste -d"," -s "$REPO_DIR/$uni" | sed 's/^/"/g' | sed 's/$/"/g')
    echo "bash \"$MYDRONE\" histo eod --weekend -d 2000-01-01 $extra -i $tickers" | bash | dos2unix | sed 's/_PX_LAST//g' > "$out"
    cut -d";" -f1 "$out" | tail
    upload "$out"
}

fetch_single() {
    local ticker=$1 out=$2
    bash "$MYDRONE" histo eod --weekend -d 2000-01-01 -i "$ticker" | dos2unix | sed 's/_PX_LAST//g' > "$out"
    cut -d";" -f1 "$out" | tail
    upload "$out"
}

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> CTY_YC2Y10${RESET}"
fetch_uni UNI_CTY_YC2Y10.csv CTY_YC2Y10.csv

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> FUT_PRC${RESET}"
fetch_uni UNI_FUT.csv RAW_FUT_PRC.csv

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> FUT_CVL${RESET}"
fetch_uni UNI_FUT.csv RAW_FUT_CVL.csv "-f CONTRACT_VALUE"

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> ETF_PRC${RESET}"
fetch_uni UNI_ETF_AZ.csv RAW_ETF_PRC_AZ.csv

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> CCY SYM — FX rates${RESET}"
bash "$REPO_DIR/get_BBG_ECO.sh" SYM
mv RAW_CCY_SYM.csv RAW_CCY_PRC.csv
upload RAW_CCY_PRC.csv

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> CCY ECO fields${RESET}"
if $UPLOAD; then
    bash "$REPO_DIR/get_BBG_ECO.sh" --upload
else
    bash "$REPO_DIR/get_BBG_ECO.sh"
fi

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> FXCTEM8${RESET}"
fetch_single "FXCTEM8 Index" FXCTEM8.csv

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
echo -e "\n${CYAN}>>> VIX${RESET}"
fetch_single "VIX Index" VIX.csv
