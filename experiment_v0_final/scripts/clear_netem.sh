#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if tc qdisc show dev lo | grep -q '^qdisc netem 7e00: root'; then
    privileged tc qdisc del dev lo root handle 7e00:
fi
require_clean_loopback
tc qdisc show dev lo
