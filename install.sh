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

HOOK_PATH="$HOOK" SETTINGS_PATH="$SETTINGS" MODE="$MODE" python3 - <<'PY'
import json, os, shutil, sys

hook = os.environ["HOOK_PATH"]
path = os.environ["SETTINGS_PATH"]
mode = os.environ["MODE"]

# SessionStart matches on `source`; SubagentStart matches on `agent_type`, where
# "*" means every agent type. SubagentStart only accepts context as JSON, hence
# --json.
EVENTS = {
    "SessionStart": ("startup|resume|clear|compact", hook),
    "SubagentStart": ("*", hook + " --json"),
}

if os.path.exists(path):
    with open(path) as f:
        text = f.read().strip()
    try:
        settings = json.loads(text) if text else {}
    except json.JSONDecodeError as e:
        sys.exit(f"install.sh: {path} is not valid JSON ({e}); fix it and re-run")
    if not isinstance(settings, dict):
        sys.exit(f"install.sh: {path} must contain a JSON object")
    shutil.copyfile(path, path + ".bak")
else:
    settings = {}

hooks = settings.setdefault("hooks", {})
if not isinstance(hooks, dict):
    sys.exit(f"install.sh: 'hooks' in {path} must be a JSON object")

def ours(cmd):
    """Any hook this installer wrote, including from an older clone or name."""
    return (
        "hooks/load-rules.sh" in cmd
        or "hooks/session-start.sh" in cmd
        or ".cursor/rules/*.mdc" in cmd
    )


removed = 0
for event, (matcher, command) in EVENTS.items():
    kept = []
    for entry in hooks.get(event) or []:
        inner = entry.get("hooks", []) if isinstance(entry, dict) else []
        survivors = [h for h in inner if not ours(str(h.get("command", "")))]
        removed += len(inner) - len(survivors)
        if survivors:
            kept.append({**entry, "hooks": survivors})
        elif not inner:
            kept.append(entry)

    if mode == "install":
        kept.append({
            "matcher": matcher,
            "hooks": [{"type": "command", "command": command}],
        })

    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)

if not hooks:
    settings.pop("hooks", None)

with open(path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

if mode == "install":
    print(f"Installed {' + '.join(EVENTS)} hooks -> {hook}")
    if removed:
        print(f"Replaced {removed} previously installed hook entr{'y' if removed == 1 else 'ies'}.")
else:
    print(f"Removed {removed} hook entr{'y' if removed == 1 else 'ies'} from {path}.")
print(f"Settings: {path}")
PY

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
