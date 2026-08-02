#!/usr/bin/env python3
"""Add or remove hook entries in a Claude Code settings file.

Reads one JSON request on stdin:

    {"settings": "/path/to/settings.json",
     "tag": "hooks/load-rules.sh",
     "mode": "install" | "uninstall",
     "entries": [{"event": "SessionStart", "matcher": "startup", "command": "..."}]}

`tag` is what identifies entries a previous run wrote: every hook command
containing it is removed first, across every event. That makes re-running
idempotent, and means moving the clone or changing which events a hook binds to
cannot strand an entry pointing at the old path.

Every other setting is preserved, and an existing file is copied to
<settings>.bak before it is rewritten.
"""

import json
import os
import shutil
import sys


def die(message):
    sys.exit(f"write-settings-hook.py: {message}")


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        text = f.read().strip()
    try:
        settings = json.loads(text) if text else {}
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON ({e}); fix it and re-run")
    if not isinstance(settings, dict):
        die(f"{path} must contain a JSON object")
    shutil.copyfile(path, path + ".bak")
    return settings


def strip_tagged(hooks, tag):
    """Drop every hook command containing `tag`; return how many went."""
    removed = 0
    for event in list(hooks):
        kept = []
        for entry in hooks.get(event) or []:
            inner = entry.get("hooks", []) if isinstance(entry, dict) else []
            survivors = [h for h in inner if tag not in str(h.get("command", ""))]
            removed += len(inner) - len(survivors)
            if survivors:
                kept.append({**entry, "hooks": survivors})
            elif not inner:
                kept.append(entry)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return removed


def main():
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        die(f"stdin is not valid JSON ({e})")

    path = request["settings"]
    tag = request["tag"]
    mode = request.get("mode", "install")
    entries = request.get("entries", [])

    settings = load(path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        die(f"'hooks' in {path} must be a JSON object")

    removed = strip_tagged(hooks, tag)

    if mode == "install":
        for entry in entries:
            hooks.setdefault(entry["event"], []).append({
                "matcher": entry["matcher"],
                "hooks": [{"type": "command", "command": entry["command"]}],
            })

    if not hooks:
        settings.pop("hooks", None)

    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    plural = "y" if removed == 1 else "ies"
    if mode == "install":
        events = " + ".join(e["event"] for e in entries)
        print(f"Installed {events} hooks -> {tag}")
        if removed:
            print(f"Replaced {removed} previously installed hook entr{plural}.")
    else:
        print(f"Removed {removed} hook entr{plural} from {path}.")
    print(f"Settings: {path}")


main()
