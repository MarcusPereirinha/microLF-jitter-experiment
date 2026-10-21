#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/config/experiment.env"
source "$ROOT/config/toolchain.env"
export PERIOD_MS MAXWAIT_MS WARMUP_EVENTS MEASURED_EVENTS GRACE_PERIOD_MS
export BASE_DELAY_MS REPETITIONS MASTER_SEED BOOTSTRAP_SEED BOOTSTRAP_RESAMPLES
export PILOT_REPETITIONS PILOT_LOW_PCT PILOT_HIGH_PCT
privileged() {
    if [[ $EUID -eq 0 ]]; then "$@"; else sudo -n "$@"; fi
}
require_clean_loopback() {
    tc -j qdisc show dev lo | python3 -c 'import json,sys; q=json.load(sys.stdin); sys.exit(0 if q and all(x.get("kind")=="noqueue" for x in q) else 1)' || {
        echo 'BLOCKED: lo has an existing qdisc. Preserving it.' >&2
        return 1
    }
}
