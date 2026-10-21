#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
python3 "$ROOT/scripts/campaign.py" check-frozen
campaign=${1:-final_$(date -u +%Y%m%dT%H%M%S)}
plan=$(python3 "$ROOT/scripts/campaign.py" plan final "$campaign")
printf '%s\n' "$campaign" >"$ROOT/logs/active_final.txt"
while IFS=, read -r scenario delay jitter rep seed; do
    [[ $scenario == scenario ]] && continue
    python3 "$ROOT/scripts/campaign.py" check-frozen
    bash "$ROOT/scripts/run_one.sh" "$scenario" "$delay" "$jitter" "$rep" "$seed" final "$campaign"
done <"$plan"
"$ANALYSIS_PYTHON" "$ROOT/scripts/analyze.py" --campaign "$campaign"
printf '%s\n' "$campaign" >"$ROOT/logs/completed_final.txt"
python3 "$ROOT/scripts/final_audit.py"
python3 "$ROOT/scripts/write_report.py"
python3 "$ROOT/scripts/final_audit.py" --manifest
