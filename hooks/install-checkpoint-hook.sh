#!/bin/sh
# Install (or remove) the Stop hook that nudges a checkpoint when context is
# large and the session never went idle enough to trip usage-gate.sh's own
# idle-based trigger.
#
#   ./install-checkpoint-hook.sh              install / update the hook
#   ./install-checkpoint-hook.sh --uninstall  remove it
#   ./install-checkpoint-hook.sh --help
#
# Separate from install-usage-hook.sh: it shares that hook's log and helper
# module but fires on a different event, and either can be installed, re-run,
# or removed without disturbing the other.
#
# Works from any clone location: the hook is registered with the absolute path
# of *this* checkout. Re-run it after moving the clone.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOK="$SCRIPT_DIR/checkpoint-stop.sh"
MODE=install

for arg in "$@"; do
	case "$arg" in
		--uninstall) MODE=uninstall ;;
		-h|--help)
			awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
			exit 0
			;;
		*)
			echo "install-checkpoint-hook.sh: unknown option '$arg' (try --help)" >&2
			exit 2
			;;
	esac
done

command -v python3 >/dev/null 2>&1 || {
	echo "install-checkpoint-hook.sh: python3 is required to edit settings.json safely" >&2
	exit 1
}

[ -f "$HOOK" ] || {
	echo "install-checkpoint-hook.sh: hook script not found at $HOOK" >&2
	exit 1
}
chmod +x "$HOOK"

CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
SETTINGS="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"

HOOK_PATH="$HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": "hooks/checkpoint-stop.sh",
    "mode": os.environ["MODE"],
    "entries": [{"event": "Stop", "matcher": "", "command": os.environ["HOOK_PATH"]}],
}))' | python3 "$SCRIPT_DIR/write-settings-hook.py"

if [ "$MODE" = install ]; then
	echo "Done. The hook fires at the end of the next turn."
fi
