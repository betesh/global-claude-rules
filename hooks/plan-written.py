#!/usr/bin/env python3
"""Nudge toward /clear when a plan file is written whole.

Registered by install-hooks.sh:

    PostToolUse  Write  ./plan-written.py   JSON stdout becomes context

Writing a plan is the moment a session's context is worth least and costs most:
what matters has just been made durable in a file, and the conversation that
produced it will be re-sent with every request of the implementation that
follows. That is the same carried-history cost measured as the largest single
term in a credit window.

Why a hook and not a rule: a rule in ../rules is re-read on every request of
every session, about 0.4 points of a window per 1,000 tokens. This costs nothing
until the moment it applies, and it cannot be forgotten.

Only `Write` is matched, not `Edit`. Deleting finished items from a plan is
routine housekeeping on the way to a commit; replacing the file wholesale is a
new plan or a rewritten one.

Never fails a tool call: any error exits 0 with no output.
"""

import json
import os
import sys

MESSAGE = (
    "A plan file was just written whole. Before doing anything else: make sure everything "
    "learned in this conversation is durable — the plan reflects what is left, and anything "
    "learned about the repo is written into the repo — then commit, then tell the user plainly "
    "that this is a good moment to /clear, and why: implementing from a fresh session re-sends "
    "the plan instead of the conversation that produced it, and context is charged on every "
    "request. Do not start implementing in the same breath."
)


def main():
    payload = json.load(sys.stdin)
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    parts = os.path.normpath(path).split(os.sep)
    if "docs" not in parts or parts.index("docs") + 1 >= len(parts):
        return
    if parts[parts.index("docs") + 1] != "plans":
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": MESSAGE,
        }
    }))


try:
    main()
except Exception:
    sys.exit(0)
