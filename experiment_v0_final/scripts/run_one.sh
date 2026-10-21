#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $# -ge 5 && $# -le 7 ]] || { echo 'Usage: run_one.sh SCENARIO DELAY JITTER REP SEED [PHASE] [CAMPAIGN]'; exit 64; }
export SCENARIO=$1 RUN_DELAY=$2 RUN_JITTER=$3 REPETITION=$4 RUN_SEED=$5
export PHASE=${6:-manual} CAMPAIGN_ID=${7:-manual}
[[ $SCENARIO =~ ^(B0|C[0-3]|PROBE)$ && $PHASE =~ ^(sanity|probe|pilot|final|manual)$ && $CAMPAIGN_ID =~ ^[a-zA-Z0-9_-]+$ ]] || exit 64
for arg in "$RUN_DELAY" "$RUN_JITTER" "$REPETITION" "$RUN_SEED"; do [[ $arg =~ ^[0-9]+$ ]] || exit 64; done
if [[ $SCENARIO == B0 ]]; then [[ $RUN_DELAY == 0 && $RUN_JITTER == 0 ]] || exit 64; fi
if [[ $SCENARIO =~ ^C([0-3])$ ]]; then
    [[ $RUN_DELAY -eq $BASE_DELAY_MS && $RUN_JITTER -eq $((BASH_REMATCH[1] * 5)) ]] || exit 64
fi
exec 7>"$ROOT/logs/.run.lock"
flock -n 7 || { echo 'Another run is active'; exit 1; }
require_clean_loopback
run_id="${SCENARIO}_rep$(printf '%02d' "$REPETITION")_$(date -u +%Y%m%dT%H%M%S%N)"
export RUN_DIR="$ROOT/results/raw/$PHASE/$CAMPAIGN_ID/$run_id"
mkdir -p "$RUN_DIR"
echo "RUN_START $RUN_DIR"
set +e
if [[ $SCENARIO == B0 ]]; then
    tc qdisc show dev lo >"$RUN_DIR/tc_applied.txt"
    tc -j qdisc show dev lo >"$RUN_DIR/tc_applied.json"
    python3 "$ROOT/scripts/launch_federates.py" "$RUN_DIR"
    rc=$?
    tc -s qdisc show dev lo >"$RUN_DIR/tc_after.txt"
    tc qdisc show dev lo >"$RUN_DIR/tc_cleared.txt"
else
    bash "$ROOT/scripts/apply_netem.sh" "$RUN_DELAY" "$RUN_JITTER" "$RUN_SEED" -- \
        python3 "$ROOT/scripts/launch_federates.py" "$RUN_DIR"
    rc=$?
fi
set -e
printf '{"exit_code":%d}\n' "$rc" >"$RUN_DIR/infrastructure.json"
python3 "$ROOT/scripts/analyze.py" --validate "$RUN_DIR"
echo "RUN_END $run_id"
