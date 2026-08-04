#!/bin/sh
# Warns (never blocks) once one file's cumulative Edit payload this session
# would have cost more than rewriting it once. install-hooks.sh registers it:
#
#   PreToolUse  ./edit-payload-warn.sh   matcher "Edit"   JSON stdout can add context
#
# Any error exits 0 with no output: a bug here must never be able to block a
# tool call.
#
# Locates its own repo, so the clone can live anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/edit_payload_warn.py"
exit 0
