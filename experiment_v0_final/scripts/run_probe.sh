#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
campaign=${1:-probe_$(date -u +%Y%m%dT%H%M%S)}
# Deliberate STP violation via real network delay; no reaction waits.
bash "$ROOT/scripts/run_one.sh" PROBE 80 0 1 "$MASTER_SEED" probe "$campaign"
python3 "$ROOT/scripts/campaign.py" probe-check "$campaign"
