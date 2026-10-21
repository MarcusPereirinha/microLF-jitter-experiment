#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
campaign=${1:-pilot_$(date -u +%Y%m%dT%H%M%S)}
python3 - "$ROOT" <<'PY'
import json,pathlib,sys
r=pathlib.Path(sys.argv[1])
assert json.loads((r/'logs/probe_pass.json').read_text())['pass_probe'], 'Tardy probe required'
assert any(json.loads(p.read_text()).get('valid') for p in (r/'results/raw/sanity').rglob('validation.json')), 'Baseline required'
PY
plan=$(python3 "$ROOT/scripts/campaign.py" plan pilot "$campaign")
while IFS=, read -r scenario delay jitter rep seed; do
    [[ $scenario == scenario ]] && continue
    bash "$ROOT/scripts/run_one.sh" "$scenario" "$delay" "$jitter" "$rep" "$seed" pilot "$campaign"
done <"$plan"
python3 "$ROOT/scripts/campaign.py" pilot-decision "$campaign"
