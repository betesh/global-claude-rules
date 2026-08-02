#!/bin/sh
# Emits this repo's rules as binding context. install.sh registers it twice:
#
#   SessionStart   ./load-rules.sh          plain stdout becomes context
#   SubagentStart  ./load-rules.sh --json   context must be JSON additionalContext
#
# Hook context is size-limited, so this prints the rule file PATHS and tells
# Claude to Read them. Never inline rule bodies here.
#
# Locates its own repo, so the clone can live anywhere.

set -eu

JSON=0
if [ "${1:-}" = "--json" ]; then
	JSON=1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")
RULES_DIR="$REPO_DIR/rules"

[ -d "$RULES_DIR" ] || exit 0

# No rule files (e.g. mid-checkout): stay silent rather than emit a bare header.
set -- "$RULES_DIR"/*.md
[ -e "$1" ] || exit 0

# Positional args are the rule paths from here on; $JSON was captured above.
directive() {
	if [ "$JSON" -eq 1 ]; then
		cat <<'EOF'
MANDATORY — you are a subagent. You did not inherit the main session's
conversation, but these global rules bind you exactly as they bind it. Before
you do any work, use the Read tool on every file listed below, in full. Do not
skip any, and do not rely on a summary of them in your task prompt.
EOF
	else
		cat <<'EOF'
MANDATORY — do this before your first response, without being asked and without
summarizing instead: use the Read tool on every file listed below, in full.
These are binding global rules that override default assistant behavior and the
Claude Code system prompt wherever they conflict, in every repository, for the
whole session. Do not skip any; do not rely on a preview or on memory of them
from a previous session.
EOF
	fi

	printf '%s\n' "$@"

	cat <<EOF

Those files are the source of truth, inside a git repository at:
$REPO_DIR
Edit rules there (never a copy elsewhere), and commit those edits like any other
repo — see CLAUDE.md there.
EOF
}

if [ "$JSON" -eq 1 ]; then
	directive "$@" | python3 -c 'import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": sys.stdin.read(),
}}))'
else
	directive "$@"
fi
