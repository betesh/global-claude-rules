#!/bin/sh
# Install (or remove) the SessionStart hook that loads this repo's rules into
# every Claude Code session.
#
#   ./install.sh              install / update the hook
#   ./install.sh --uninstall  remove it
#   ./install.sh --help
#
# Works from any clone location: the hook is registered with the absolute path
# of *this* checkout. Re-run it after moving the clone.
#
# Writes only the SessionStart hook entry into your Claude Code settings file
# (~/.claude/settings.json, or $CLAUDE_CONFIG_DIR/settings.json). Every other
# setting is preserved, and the previous file is backed up alongside it.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HOOK="$SCRIPT_DIR/hooks/session-start.sh"
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
MATCHER = "startup|resume|clear|compact"

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
entries = hooks.get("SessionStart") or []


def ours(cmd):
    """Any hook this installer wrote, including from an older clone path."""
    return "hooks/session-start.sh" in cmd or ".cursor/rules/*.mdc" in cmd


kept = []
removed = 0
for entry in entries:
    inner = entry.get("hooks", []) if isinstance(entry, dict) else []
    survivors = [h for h in inner if not ours(str(h.get("command", "")))]
    removed += len(inner) - len(survivors)
    if survivors:
        kept.append({**entry, "hooks": survivors})
    elif not inner:
        kept.append(entry)

if mode == "install":
    kept.append({
        "matcher": MATCHER,
        "hooks": [{"type": "command", "command": hook}],
    })

if kept:
    hooks["SessionStart"] = kept
else:
    hooks.pop("SessionStart", None)
if not hooks:
    settings.pop("hooks", None)

with open(path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

if mode == "install":
    print(f"Installed SessionStart hook -> {hook}")
    if removed:
        print(f"Replaced {removed} previously installed hook entr{'y' if removed == 1 else 'ies'}.")
else:
    print(f"Removed {removed} hook entr{'y' if removed == 1 else 'ies'} from {path}.")
print(f"Settings: {path}")
PY

if [ "$MODE" = install ]; then
	echo "Verifying hook output..."
	"$HOOK" | head -n 1
	echo "Done. Start a new Claude Code session (or run /clear) to load the rules."
fi
