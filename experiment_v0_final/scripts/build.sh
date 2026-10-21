#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ -x "$ULFC" ]] || { echo 'Run bash scripts/setup_toolchain.sh first'; exit 1; }
python3 - "$ROOT" <<'PY'
import os, pathlib, hashlib
root = pathlib.Path(__import__('sys').argv[1])
cfg = {k: int(os.environ[k]) for k in ('PERIOD_MS','MAXWAIT_MS','WARMUP_EVENTS','MEASURED_EVENTS','GRACE_PERIOD_MS')}
cfg['TOTAL_EVENTS'] = cfg['WARMUP_EVENTS'] + cfg['MEASURED_EVENTS']
cfg['DURATION_MS'] = cfg['TOTAL_EVENTS'] * cfg['PERIOD_MS'] + cfg['GRACE_PERIOD_MS']
text = (root/'src/JitterV0.ulf.in').read_text()
for k, v in cfg.items(): text = text.replace('__'+k+'__', str(v))
assert '__' not in text
destination = root/'src/JitterV0.ulf'
if not destination.exists() or destination.read_text() != text:
    if (root/'config/frozen.json').exists():
        raise SystemExit('Parameters frozen; refusing to change source')
    destination.write_text(text)
PY
cd "$ROOT"
"$ULFC" --runtime-symlink src/JitterV0.ulf 2>&1 | tee "$ROOT/logs/build.txt"
find "$ROOT/bin" -maxdepth 3 -type f -executable -print
