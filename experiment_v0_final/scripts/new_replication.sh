#!/usr/bin/env bash
# Copy only the experimental inputs into a new, empty area; preserve this campaign.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $# -eq 1 && ! -e $1 ]] || { echo 'Usage: new_replication.sh NEW_NONEXISTENT_DIRECTORY'; exit 64; }
destination=$(realpath -m -- "$1")
mkdir -p "$destination"/{src,scripts,config,logs,results/{raw,processed,figures}}
cp "$ROOT"/src/*.in "$destination/src/"
cp "$ROOT"/scripts/*.sh "$ROOT"/scripts/*.py "$destination/scripts/"
cp "$ROOT/config/experiment.env" "$ROOT/config/toolchain.env" "$destination/config/"
cp "$ROOT/requirements.txt" "$ROOT/README.md" "$ROOT/EXPERIMENT_SPEC.md" "$destination/"
printf 'Fresh replication inputs copied from %s; no observations or frozen binaries copied.\n' "$ROOT" >"$destination/logs/replication_origin.txt"
printf 'Run from %s:\n' "$destination"
printf '%s\n' 'bash scripts/setup_toolchain.sh' 'bash scripts/check_env.sh --inspect' \
    'bash scripts/build.sh' 'bash scripts/run_one.sh B0 0 0 1 20261020 sanity implementation' \
    'bash scripts/campaign_terminal.sh'
