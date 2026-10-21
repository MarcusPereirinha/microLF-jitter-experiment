#!/usr/bin/env bash
# Default: inspect only. --netem-test: temporary, privileged test on loopback.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -f "$ROOT/config/toolchain.env" ]]; then source "$ROOT/config/toolchain.env"; fi
MODE=${1:---inspect}
if [[ $# -gt 1 || ( "$MODE" != --inspect && "$MODE" != --netem-test ) ]]; then
    echo 'Usage: bash scripts/check_env.sh [--inspect|--netem-test]' >&2
    exit 64
fi
mkdir -p "$ROOT/logs"
command -v flock >/dev/null || { echo 'FAIL: flock required'; exit 1; }
exec 9>"$ROOT/logs/.audit.lock"
flock -n 9 || { echo 'FAIL: another audit is running'; exit 1; }
AUDIT=$(mktemp "$ROOT/logs/environment.XXXXXXXX.txt")
exec > >(tee "$AUDIT" "$ROOT/logs/environment.txt") 2>&1
echo "Audit UTC: $(date -u +%FT%TZ)"
echo "Mode: $MODE"
echo "Workspace: $ROOT"
echo "User: $(id)"
uname -a
cat /etc/os-release
failures=0
for name in gcc cmake git python3 tc java modprobe; do
    if command -v "$name"; then :; else
        echo "MISSING: $name"
        failures=$((failures + 1))
    fi
done
gcc --version || true
cmake --version || true
git --version || true
python3 --version || true
tc -V || true
java -version || true
echo '--- Workspace preservation ---'
if git -C "$ROOT" rev-parse --show-toplevel; then
    git -C "$ROOT" status --short --branch
    git -C "$ROOT" rev-parse HEAD || true
else
    echo 'Workspace is not a Git repository; no existing commit or branch.'
fi
echo '--- micro-LF toolchain ---'
compiler=${ULFC:-}
if [[ -z "$compiler" ]]; then
    compiler=$(command -v ulfc || command -v ulfc-dev || true)
fi
if [[ -z "$compiler" && -n ${REACTOR_UC_PATH:-} && -x ${REACTOR_UC_PATH}/ulf/bin/ulfc-dev ]]; then
    compiler=${REACTOR_UC_PATH}/ulf/bin/ulfc-dev
fi
if [[ -n "$compiler" && -x "$compiler" ]]; then
    echo "ULFC: $compiler"
    "$compiler" --version || { echo 'FAIL: compiler version command'; failures=$((failures + 1)); }
else
    echo 'MISSING: ulfc/ulfc-dev. Set ULFC to the actual micro-LF compiler.'
    failures=$((failures + 1))
fi
for name in REACTOR_UC_PATH ULF_POSIX_TEMPLATE_PATH; do
    location=${!name:-}
    echo "$name=${location:-NOT_SET}"
    if [[ -n "$location" && -d "$location" ]]; then
        git -C "$location" rev-parse HEAD || true
        git -C "$location" status --short || true
        git -C "$location" submodule status --recursive || true
    fi
done
if [[ -x /home/vinipjr/.local/bin/lfc ]]; then
    echo 'Other compiler (lfc does not establish micro-LF support):'
    /home/vinipjr/.local/bin/lfc --version || true
fi
echo '--- NetEm inspection (no network mutation) ---'
tc qdisc show dev lo
tc -s qdisc show dev lo
if [[ -r /proc/config.gz ]]; then
    # Python avoids SIGPIPE from zcat under pipefail.
    python3 -c 'import gzip; print("".join(x for x in gzip.open("/proc/config.gz", "rt") if "CONFIG_NET_SCH_NETEM" in x), end="")'
fi
modinfo sch_netem || true
echo '--- tc local NetEm syntax ---'
# The help keyword is parsed before any netlink mutation request.
tc qdisc add dev lo root netem help || true
echo '--- Privilege availability ---'
sudo_ready=0
if [[ $EUID -eq 0 ]]; then
    sudo_ready=1
elif sudo -n true; then
    sudo_ready=1
else
    echo 'BLOCKED: sudo requires interactive authentication; no qdisc was changed.'
fi
if [[ "$MODE" == --inspect ]]; then
    echo 'NetEm operational support: NOT TESTED (inspection mode).'
    echo "Toolchain prerequisite failures: $failures"
    echo "Saved: $AUDIT"
    [[ $failures -eq 0 && $sudo_ready -eq 1 ]] || exit 1
    exit 0
fi
if [[ $sudo_ready -ne 1 ]]; then
    echo 'Manual action in Ubuntu, from experiment_v0_final:'
    echo 'sudo -v && bash scripts/check_env.sh --netem-test'
    exit 2
fi
privileged() {
    if [[ $EUID -eq 0 ]]; then "$@"; else sudo -n "$@"; fi
}
# Never replace a user's pre-existing root qdisc.
tc -j qdisc show dev lo | python3 -c 'import json,sys; q=json.load(sys.stdin); sys.exit(0 if q and all(x.get("kind")=="noqueue" for x in q) else 1)' || {
    echo 'BLOCKED: existing qdisc on lo; preserving it.'
    exit 3
}
echo 'WARNING: temporary NetEm on lo affects other local traffic, including control traffic.'
owned=0
cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    if [[ $owned -eq 1 ]]; then
        if tc qdisc show dev lo | grep -q '^qdisc netem 7e00: root'; then
            if ! privileged tc qdisc del dev lo root handle 7e00:; then
                echo 'FAIL: cleanup; execute sudo tc qdisc del dev lo root handle 7e00:'
                rc=1
            fi
        fi
    fi
    echo '--- Final loopback qdisc ---'
    tc qdisc show dev lo || rc=1
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
privileged modprobe sch_netem || {
    echo 'FAIL: could not load sch_netem; jitter experiment stopped.'
    exit 1
}
owned=1
# add, rather than replace, preserves an existing configuration on races.
if ! privileged tc qdisc add dev lo root handle 7e00: netem delay 10ms; then
    echo 'FAIL: NetEm application. No jitter experiment may proceed.'
    echo 'If the kernel reports an unknown qdisc kind, record lack of NetEm support.'
    exit 1
fi
tc qdisc show dev lo
tc -s qdisc show dev lo
tc qdisc show dev lo | grep -E '^qdisc netem 7e00: root .*delay 10(ms|\.0ms)' >/dev/null
privileged tc qdisc del dev lo root handle 7e00:
owned=0
tc -j qdisc show dev lo | python3 -c 'import json,sys; q=json.load(sys.stdin); sys.exit(0 if q and all(x.get("kind")=="noqueue" for x in q) else 1)'
printf '{"netem_applied":true,"delay_ms":10,"cleanup_verified":true,"utc":"%s"}\n' "$(date -u +%FT%TZ)" >"$ROOT/logs/netem_probe.json"
echo 'NetEm: PASS (10 ms applied, inspected and immediately removed).'
echo "Toolchain prerequisite failures: $failures"
echo "Saved: $AUDIT"
[[ $failures -eq 0 ]] || exit 1
