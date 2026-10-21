#!/usr/bin/env bash
# Run from a visible terminal so the user can type sudo credentials locally.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
echo 'Autenticacao sudo para probe, piloto e campanha V0. Nao altere parametros durante a execucao.'
sudo -v
campaign="v0_$(date -u +%Y%m%dT%H%M%S)"
if [[ -f "$ROOT/logs/campaign_terminal.txt" ]]; then
    cp -n "$ROOT/logs/campaign_terminal.txt" "$ROOT/logs/campaign_previous_${campaign}.txt"
fi
set +e
(
    set -e
    bash "$ROOT/scripts/run_probe.sh" "${campaign}_probe"
    bash "$ROOT/scripts/run_pilot.sh" "${campaign}_pilot"
    bash "$ROOT/scripts/run_all.sh" "${campaign}_final"
) 2>&1 | tee "$ROOT/logs/campaign_${campaign}.txt" "$ROOT/logs/campaign_terminal.txt"
rc=${PIPESTATUS[0]}
printf '%s\n' "$rc" >"$ROOT/logs/campaign_terminal.exit"
echo "Execucao encerrada: $rc. Logs preservados."
read -r -p 'Enter para fechar: ' unused || true
exit "$rc"
