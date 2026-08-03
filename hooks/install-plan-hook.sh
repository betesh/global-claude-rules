#!/bin/sh
# Install (or remove) the PostToolUse hook that nudges toward /clear when a
# plan file is written whole.
#
#   ./install-plan-hook.sh              install / update the hook
#   ./install-plan-hook.sh --uninstall  remove it
#   ./install-plan-hook.sh --help
#
# Separate from install-usage-hook.sh because it is separately useful: either
# can be installed, re-run, or removed without disturbing the other.
#
# Works from any clone location: the hook is registered with the absolute path
# of *this* checkout. Re-run it after moving the clone.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOK="$SCRIPT_DIR/plan-written.py"
MODE=install

for arg in "$@"; do
	case "$arg" in
		--uninstall) MODE=uninstall ;;
		-h|--help)
			awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
			exit 0
			;;
		*)
			echo "install-plan-hook.sh: unknown option '$arg' (try --help)" >&2
			exit 2
			;;
	esac
done

command -v python3 >/dev/null 2>&1 || {
	echo "install-plan-hook.sh: python3 is required to edit settings.json safely" >&2
	exit 1
}

[ -f "$HOOK" ] || {
	echo "install-plan-hook.sh: hook script not found at $HOOK" >&2
	exit 1
}
chmod +x "$HOOK"

CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
SETTINGS="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"

HOOK_PATH="$HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
hook = os.environ["HOOK_PATH"]
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": "hooks/plan-written.py",
    "mode": os.environ["MODE"],
    "entries": [{"event": "PostToolUse", "matcher": "Write", "command": "python3 " + hook}],
}))' | python3 "$SCRIPT_DIR/write-settings-hook.py"

if [ "$MODE" = install ]; then
	echo "Done. The hook fires on the next Write to a plan file."
fi
