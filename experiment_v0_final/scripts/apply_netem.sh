#!/usr/bin/env bash
# Scoped NetEm: always run a command and remove our qdisc before returning.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $# -ge 5 && $4 == -- ]] || { echo 'Usage: apply_netem.sh BASE JITTER SEED -- COMMAND...'; exit 64; }
delay=$1 jitter=$2 seed=$3
shift 4
[[ $delay =~ ^[0-9]+$ && $jitter =~ ^[0-9]+$ && $seed =~ ^[0-9]+$ ]] || exit 64
exec 8>"$ROOT/logs/.netem.lock"
flock -n 8 || { echo 'NetEm already in use by this experiment'; exit 1; }
require_clean_loopback
privileged true
echo "WARNING: NetEm on lo affects other local traffic. delay=${delay}ms jitter=${jitter}ms seed=$seed"
cleanup() {
    rc=$?
    trap - EXIT INT TERM
    bash "$ROOT/scripts/clear_netem.sh" >"${RUN_DIR:?}/tc_cleared.txt" 2>&1 || rc=1
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
options=(delay "${delay}ms")
if [[ $jitter -gt 0 ]]; then options+=("${jitter}ms" distribution normal); fi
# This installed tc supports seed; support was established in environment.txt.
printf '%q ' tc qdisc add dev lo root handle 7e00: netem "${options[@]}" seed "$seed" >"$RUN_DIR/tc_command.txt"
printf '\n' >>"$RUN_DIR/tc_command.txt"
privileged tc qdisc add dev lo root handle 7e00: netem "${options[@]}" seed "$seed"
{ tc qdisc show dev lo; tc -s qdisc show dev lo; } >"$RUN_DIR/tc_applied.txt"
tc -j qdisc show dev lo >"$RUN_DIR/tc_applied.json"
"$@"
tc -s qdisc show dev lo >"$RUN_DIR/tc_after.txt"
