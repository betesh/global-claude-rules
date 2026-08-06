#!/bin/sh
# Install (or remove) every hook this repo ships: the SessionStart credit-window
# report, the UserPromptSubmit gate, the PreToolUse gate on individual tool
# calls, the PreToolUse warning on one file's accumulating Edit payload, the
# PreCompact gate on starting a compact, and the Stop nudge to checkpoint a
# large session that never idled.
#
#   ./install-hooks.sh              install / update all six hooks
#   ./install-hooks.sh --uninstall  remove all six
#   ./install-hooks.sh --help
#
# One script because they share a single settings.json and a single
# write-settings-hook.py call: installing them together keeps that edit atomic,
# and one tag scoped to this checkout's hooks/ directory finds every entry
# regardless of which hook wrote it, so uninstall or re-run cannot strand one.
#
# Works from any clone location: hooks are registered with the absolute path of
# *this* checkout. Re-run after moving the clone.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOKS_DIR="$SCRIPT_DIR/hooks"
MODE=install

for arg in "$@"; do
	case "$arg" in
		--uninstall) MODE=uninstall ;;
		-h|--help)
			awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
			exit 0
			;;
		*)
			echo "install-hooks.sh: unknown option '$arg' (try --help)" >&2
			exit 2
			;;
	esac
done

command -v python3 >/dev/null 2>&1 || {
	echo "install-hooks.sh: python3 is required" >&2
	exit 1
}

WINDOW="$HOOKS_DIR/usage-window.sh"
GATE="$HOOKS_DIR/usage-gate.sh"
TOOLGATE="$HOOKS_DIR/usage-tool-gate.sh"
EDITWARN="$HOOKS_DIR/edit-payload-warn.sh"
COMPACTGATE="$HOOKS_DIR/usage-compact-gate.sh"
CHECKPOINT="$HOOKS_DIR/checkpoint-stop.sh"

for script in "$WINDOW" "$GATE" "$TOOLGATE" "$EDITWARN" "$COMPACTGATE" "$CHECKPOINT"; do
	[ -f "$script" ] || {
		echo "install-hooks.sh: hook script not found at $script" >&2
		exit 1
	}
done
chmod +x "$WINDOW" "$GATE" "$TOOLGATE" "$EDITWARN" "$COMPACTGATE" "$CHECKPOINT"

CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
SETTINGS="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"

# `resume` and `compact` are left out of SessionStart: they continue a session
# whose window is already reported, and re-reporting it would spend context to
# say the same thing.
WINDOW="$WINDOW" GATE="$GATE" TOOLGATE="$TOOLGATE" EDITWARN="$EDITWARN" COMPACTGATE="$COMPACTGATE" CHECKPOINT="$CHECKPOINT" \
HOOKS_DIR="$HOOKS_DIR" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 -c '
import json, os
print(json.dumps({
    "settings": os.environ["SETTINGS_PATH"],
    "tag": os.environ["HOOKS_DIR"] + "/",
    "mode": os.environ["MODE"],
    "entries": [
        {"event": "SessionStart", "matcher": "startup|clear",
         "command": os.environ["WINDOW"]},
        {"event": "UserPromptSubmit", "matcher": "",
         "command": os.environ["GATE"]},
        {"event": "PreToolUse", "matcher": "",
         "command": os.environ["TOOLGATE"]},
        {"event": "PreToolUse", "matcher": "Edit",
         "command": os.environ["EDITWARN"]},
        {"event": "PreCompact", "matcher": "",
         "command": os.environ["COMPACTGATE"]},
        {"event": "Stop", "matcher": "",
         "command": os.environ["CHECKPOINT"]},
    ],
}))' | python3 "$HOOKS_DIR/write-settings-hook.py"

if [ "$MODE" = install ]; then
	echo "Verifying hook output..."
	"$WINDOW" </dev/null | sed 's/^/  | /'
	echo
	echo "Verifying the prompt gate..."
	# Capture before printing: in a pipeline the status is sed's, not the gate's,
	# so piping straight to sed would report every run as a pass.
	GATE_OUT=$("$GATE" </dev/null 2>&1) && GATE_STATUS=0 || GATE_STATUS=$?
	[ -n "$GATE_OUT" ] && printf '%s\n' "$GATE_OUT" | sed 's/^/  | /'
	if [ "$GATE_STATUS" -eq 2 ]; then
		echo "  | (exit 2 — prompts are dropped until the window renews)"
	else
		echo "  | (exit 0 — prompts are being sent)"
	fi
	echo
	echo "Verifying the tool gate..."
	TOOLGATE_OUT=$("$TOOLGATE" </dev/null 2>&1)
	if [ -n "$TOOLGATE_OUT" ]; then
		printf '%s\n' "$TOOLGATE_OUT" | sed 's/^/  | /'
		echo "  | (a decision printed with no transcript on stdin — check usage_tool_gate.py)"
	else
		echo "  | (no output with no transcript on stdin — tool calls are allowed)"
	fi
	echo
	echo "Verifying the edit-payload warning..."
	EDITWARN_OUT=$("$EDITWARN" </dev/null 2>&1)
	if [ -n "$EDITWARN_OUT" ]; then
		printf '%s\n' "$EDITWARN_OUT" | sed 's/^/  | /'
		echo "  | (a decision printed with no transcript on stdin — check edit_payload_warn.py)"
	else
		echo "  | (no output with no transcript on stdin — correct, it only fires on Edit)"
	fi
	echo
	echo "Verifying the compact gate..."
	COMPACTGATE_OUT=$("$COMPACTGATE" </dev/null 2>&1) && COMPACTGATE_STATUS=0 || COMPACTGATE_STATUS=$?
	[ -n "$COMPACTGATE_OUT" ] && printf '%s\n' "$COMPACTGATE_OUT" | sed 's/^/  | /'
	if [ "$COMPACTGATE_STATUS" -eq 2 ]; then
		echo "  | (exit 2 — compacts are refused until the window renews)"
	else
		echo "  | (exit 0 — compacts are allowed)"
	fi
	echo "Done. The window state above is what each new session will see;"
	echo "the tool gate, edit-payload warning, compact gate, and checkpoint hooks fire only when they trigger."
fi
