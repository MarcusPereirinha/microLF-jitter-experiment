#!/usr/bin/env bash
# Interactive launcher: keep authentication in the user's visible terminal.
set -u
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT" || exit 1
printf 'Continuacao V0: autenticacao sudo e teste NetEm pendente.\n'
if sudo -v; then
    bash scripts/check_env.sh --netem-test
    result=$?
else
    result=$?
fi
printf '%s\n' "$result" > logs/netem_terminal.exit
printf '\nTeste encerrado (codigo %s). Consulte logs/environment.txt.\n' "$result"
printf 'A janela pode ser fechada.\n'
read -r -p 'Enter para fechar: ' unused || true
exit "$result"
