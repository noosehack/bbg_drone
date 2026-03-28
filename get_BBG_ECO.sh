#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(dirname "$0")"
source "$REPO_DIR/blawkops_sh/blawkops.sh"

MYDRONE="$REPO_DIR/mydrone.sh"

DEFAULT_FIELDS="CESI IRS_3MTH INFL EHPI_INFL FRD_1M FRD_I1M CRI EQT_IDX_LOC EQT_IDX_USD"

UPLOAD=false
FIELDS_ARGS=()
for arg in "$@"; do
    [ "$arg" = "--upload" ] && UPLOAD=true || FIELDS_ARGS+=("$arg")
done
FIELDS="${FIELDS_ARGS[*]:-$DEFAULT_FIELDS}"
TODAY=$(date +%Y-%m-%d)

BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

for field in $FIELDS; do
    echo -e "${CYAN}>>> Getting field: $field ...${RESET}"
    tickers=$(cgrep "$REPO_DIR/ECO.csv" "^${field}$" | cut -d";" -f2 | sed 1d | paste -d"," -s | sed 's/^/"/g' | sed 's/$/"/g')
    echo "bash \"$MYDRONE\" histo eod --weekend -d 2000-01-01 -i $tickers" | bash | dos2unix | sed 's/_PX_LAST//g' > "RAW_CCY_${field}.csv"

    awk -F";" -v today="$TODAY" -v field="$field" \
        -v GREEN="\033[1;32m" \
        -v YELLOW="\033[1;33m" \
        -v RED="\033[1;31m" \
        -v RESET="\033[0m" '
    # Pass 1: ECO.csv — build ticker -> CCY lookup for this field
    NR == FNR {
        if (FNR == 1) {
            for (i = 1; i <= NF; i++) {
                if ($i == "SYM")   sym_col = i
                if ($i == field)   fld_col = i
            }
            next
        }
        if (fld_col > 0 && $fld_col != "")
            ticker_ccy[$fld_col] = $sym_col
        next
    }
    # Pass 2: header + last 10 rows of RAW_CCY_${field}.csv
    FNR == 1 {
        for (i = 2; i <= NF; i++) colname[i] = $i
        ncols = NF
        next
    }
    {
        last_date = $1
        rows++
        for (i = 2; i <= NF; i++) {
            total++
            if ($i == "NA") { nas++; col_na[i]++ }
        }
    }
    END {
        non_na  = total - nas
        date_ok = (last_date == today)
        data_ok = (non_na > 0)

        if (date_ok && data_ok)
            printf "    %sdata verification = ok!%s  (latest: %s, non-NA values: %d/%d)\n", GREEN, RESET, last_date, non_na, total
        else {
            printf "    %s*** suspicion of corrupted data ***%s\n", RED, RESET
            if (!date_ok) printf "    %s- latest date is %s  (expected %s)%s\n", RED, last_date, today, RESET
            if (!data_ok) printf "    %s- all values are NA across last 10 rows%s\n", RED, RESET
        }

        for (i = 2; i <= ncols; i++) {
            if (col_na[i] == rows) {
                ccy = ticker_ccy[colname[i]]
                if (ccy != "")
                    printf "    %s! warning: all NA  %-30s  CCY: %s%s\n", YELLOW, colname[i], ccy, RESET
                else
                    printf "    %s! warning: all NA  %s%s\n", YELLOW, colname[i], RESET
            }
        }
    }
    ' "$REPO_DIR/ECO.csv" <(head -1 "RAW_CCY_${field}.csv"; locf "RAW_CCY_${field}.csv" | tail -10)

    # rename column headers from Bloomberg tickers to CCY names (skip for SYM — it IS the reference)
    if [ "$field" != "SYM" ] && [ -f RAW_CCY_PRC.csv ]; then
        headerfromto RAW_CCY_PRC.csv "RAW_CCY_${field}.csv" > tmp.csv
        mv tmp.csv "RAW_CCY_${field}.csv"
    fi

    if $UPLOAD; then
        echo -e "    ${GREEN}↑ uploading RAW_CCY_${field}.csv ...${RESET}"
        bash "$REPO_DIR/scpaws-eu_upload.sh" "RAW_CCY_${field}.csv"
    fi

done
