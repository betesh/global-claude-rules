#!/bin/sh
# Decides whether a /compact is worth starting, before it runs.
# install-hooks.sh registers it:
#
#   PreCompact  ./usage-compact-gate.sh   exit 2 cancels the compact
#
# A compact reaches the API like any other request and can spend real tokens
# even when it fails (usage/notes.md), so a window nearly out of credit is a
# bad moment to start one. Same exit-code convention as usage-gate.sh:
#
#   2  credit is gone; the harness cancels the compact and shows our stderr
#   0  let it run
#
# Locates its own repo, so the clone can live anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/usage_compact_gate.py"
[ $? -eq 2 ] && exit 2
exit 0
