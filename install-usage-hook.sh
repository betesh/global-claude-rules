#!/bin/sh
# Install (or remove) the SessionStart hook that reports the shared credit
# window before the model runs.
#
#   ./install-usage-hook.sh              install / update the hook
#   ./install-usage-hook.sh --uninstall  remove it
#   ./install-usage-hook.sh --help
#
# Separate from install.sh because it is separately useful: the rules bind
# without it, and it reads your session transcripts, which not everyone will
# want. Both installers touch only their own entries, so either can be run,
# re-run, or removed without disturbing the other.
#
# Works from any clone location: the hook is registered with the absolute path
# of *this* checkout. Re-run it after moving the clone.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOK="$SCRIPT_DIR/hooks/usage-window.sh"
MODE=install

for arg in "$@"; do
	case "$arg" in
		--uninstall) MODE=uninstall ;;
		-h|--help)
			awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
			exit 0
			;;
		*)
			echo "install-usage-hook.sh: unknown option '$arg' (try --help)" >&2
			exit 2
			;;
	esac
done

command -v python3 >/dev/null 2>&1 || {
	echo "install-usage-hook.sh: python3 is required" >&2
	exit 1
}

[ -f "$HOOK" ] || {
	echo "install-usage-hook.sh: hook script not found at $HOOK" >&2
	exit 1
}
chmod +x "$HOOK"

CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
SETTINGS="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"

# `resume` and `compact` are left out: they continue a session whose window is
# already reported, and re-reporting it would spend context to say the same
# thing.
HOOK_PATH="$HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": "hooks/usage-window.sh",
    "mode": os.environ["MODE"],
    "entries": [
        {"event": "SessionStart", "matcher": "startup|clear",
         "command": os.environ["HOOK_PATH"]},
    ],
}))' | python3 "$SCRIPT_DIR/hooks/write-settings-hook.py"

if [ "$MODE" = install ]; then
	echo "Verifying hook output..."
	"$HOOK" </dev/null | sed 's/^/  | /'
	echo "Done. The window state above is what each new session will see."
fi
