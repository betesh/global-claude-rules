#!/bin/sh
# Install (or remove) the hooks that load this repo's rules into every Claude
# Code session — SessionStart for the main session, SubagentStart for every
# subagent spawned with the Agent tool.
#
#   ./install.sh              install / update the hook
#   ./install.sh --uninstall  remove it
#   ./install.sh --help
#
# Works from any clone location: the hook is registered with the absolute path
# of *this* checkout. Re-run it after moving the clone.
#
# Writes only those two hook entries into your Claude Code settings file
# (~/.claude/settings.json, or $CLAUDE_CONFIG_DIR/settings.json). Every other
# setting is preserved, and the previous file is backed up alongside it.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOK="$SCRIPT_DIR/hooks/load-rules.sh"
MODE=install

for arg in "$@"; do
	case "$arg" in
		--uninstall) MODE=uninstall ;;
		-h|--help)
			awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
			exit 0
			;;
		*)
			echo "install.sh: unknown option '$arg' (try --help)" >&2
			exit 2
			;;
	esac
done

command -v python3 >/dev/null 2>&1 || {
	echo "install.sh: python3 is required to edit settings.json safely" >&2
	exit 1
}

[ -f "$HOOK" ] || {
	echo "install.sh: hook script not found at $HOOK" >&2
	exit 1
}
chmod +x "$HOOK"

CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
SETTINGS="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"

# SessionStart matches on `source`; SubagentStart matches on `agent_type`, where
# "*" means every agent type. SubagentStart only accepts context as JSON, hence
# --json.
HOOK_PATH="$HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
hook = os.environ["HOOK_PATH"]
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": "hooks/load-rules.sh",
    "mode": os.environ["MODE"],
    "entries": [
        {"event": "SessionStart", "matcher": "startup|resume|clear|compact", "command": hook},
        {"event": "SubagentStart", "matcher": "*", "command": hook + " --json"},
    ],
}))' | python3 "$SCRIPT_DIR/hooks/write-settings-hook.py"

# Registered separately from the rules hook, under its own tag, so uninstalling
# one does not strand the other.
PLAN_HOOK="$SCRIPT_DIR/hooks/plan-written.py"
chmod +x "$PLAN_HOOK"
HOOK_PATH="$PLAN_HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
hook = os.environ["HOOK_PATH"]
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": "hooks/plan-written.py",
    "mode": os.environ["MODE"],
    "entries": [{"event": "PostToolUse", "matcher": "Write", "command": "python3 " + hook}],
}))' | python3 "$SCRIPT_DIR/hooks/write-settings-hook.py"

# Situational rules ship as skills instead: the model sees only a one-line
# description until it loads one, where a rule file costs its full length on
# every request of every session. Symlinked rather than copied, so editing the
# checkout takes effect without reinstalling.
SKILLS_SRC="$SCRIPT_DIR/skills"
SKILLS_DST="$CONFIG_DIR/skills"
if [ -d "$SKILLS_SRC" ]; then
	for skill in "$SKILLS_SRC"/*/; do
		[ -d "$skill" ] || continue
		name=$(basename "$skill")
		link="$SKILLS_DST/$name"
		# Only ever remove a link we own; a real directory there is someone else's.
		if [ -L "$link" ]; then
			rm -f "$link"
		elif [ -e "$link" ]; then
			echo "install.sh: $link exists and is not a symlink; leaving it alone" >&2
			continue
		fi
		if [ "$MODE" = install ]; then
			mkdir -p "$SKILLS_DST"
			ln -s "${skill%/}" "$link"
			echo "Linked skill: $name"
		else
			echo "Removed skill: $name"
		fi
	done
fi

if [ "$MODE" = install ]; then
	echo "Verifying hook output..."
	"$HOOK" >/dev/null
	"$HOOK" --json | python3 -c 'import json, sys
d = json.load(sys.stdin)["hookSpecificOutput"]
assert d["hookEventName"] == "SubagentStart", d
n = len(d["additionalContext"].strip().splitlines())
print(f"  ok: SessionStart text + SubagentStart JSON ({n} lines of context)")'
	echo "Done. Start a new Claude Code session (or run /clear) to load the rules."
fi
