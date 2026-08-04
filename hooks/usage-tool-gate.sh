#!/bin/sh
# Denies a tool call before it runs, once too little budget remains for
# another request. install-hooks.sh registers it:
#
#   PreToolUse  ./usage-tool-gate.sh   JSON stdout can deny the call
#
# usage-gate.sh only checks the window once per prompt; this runs before every
# individual tool call and catches a window that crosses the gate mid-flight,
# between one prompt-level check and the next.
#
# Any error exits 0 with no output: a bug here must never be able to block a
# tool call.
#
# Locates its own repo, so the clone can live anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/usage_tool_gate.py"
exit 0
