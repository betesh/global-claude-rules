#!/bin/sh
# Decides whether a prompt is worth sending, before it is sent.
# install-hooks.sh registers it:
#
#   UserPromptSubmit  ./usage-gate.sh   exit 2 drops the prompt; stdout is context
#
# The SessionStart report runs once, before a session has spent anything, so
# nothing watches the window while it actually drains. This runs on every
# prompt, off the same fitted estimate, and is the only place a spent window
# can be noticed for free — once the model is invoked the request is already
# paid for, so a rule telling it to stop cannot un-spend one.
#
# Exit codes are the whole interface:
#
#   2  credit is gone; the harness drops the prompt and shows our stderr
#   0  send it — stdout, if any, becomes context for this turn
#
# Only a deliberate 2 blocks. Any other failure — a crash, a missing python, a
# malformed log — exits 0, because a bug in accounting must never be able to
# lock someone out of their own session.
#
# Locates its own repo, so the clone can live anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/usage_gate.py"
[ $? -eq 2 ] && exit 2
exit 0
