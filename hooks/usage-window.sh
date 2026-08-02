#!/bin/sh
# Reports the state of the shared credit window as SessionStart context, and
# logs the session's own start. install-usage-hook.sh registers it:
#
#   SessionStart  ./usage-window.sh   plain stdout becomes context
#
# It runs before the model does, so everything it reports costs no request:
#
#   * the shared event log in ../usage/events.jsonl — the window start and any
#     percentage the user reported;
#   * the session transcripts under the Claude config dir, whose per-request
#     `message.usage` counts are the only local measure of what every agent on
#     this machine has actually spent;
#   * the hook payload on stdin, whose session_id tags the log line it writes and
#     is reported so the model's own appends carry the same tag.
#
# When credit is already out, that warning lands before the model can start work
# — the one moment a wait is free.
#
# Never fails a session: any error exits 0 with no output.
#
# Locates its own repo, so the clone can live anywhere.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/usage_window.py" || exit 0
