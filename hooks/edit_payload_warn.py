#!/usr/bin/env python3
"""Warn once an `Edit`'s cumulative payload on one file, this session, would
have cost more than rewriting the file once.

Registered by install-hooks.sh as a PreToolUse hook matching `Edit`:

    PreToolUse  ./edit-payload-warn.sh   JSON stdout can add context, never denies

Every `old_string`/`new_string` pair stays in context for every request that
follows it (usage/notes.md: measured cases at 1.3x-2.5x a file's own size
after a few dozen edits). Stateless like usage_tool_gate.py: it recomputes the
running total from this session's own transcript on every firing rather than
tracking a counter, so it can't drift from what actually happened.

Never blocks: a bug here, or a wrong call, must not stop an edit from landing.
Any exception exits 0 with no output.
"""

import json
import os
import sys

import usage_common as uc


def payload_len(tool_input):
    return len(tool_input.get("old_string") or "") + len(tool_input.get("new_string") or "")


def prior_payload(transcript_path, file_path):
    """Sum of old_string+new_string lengths for every earlier Edit on this
    file in this session's own transcript."""
    total = 0
    try:
        with open(transcript_path, errors="replace") as f:
            for line in f:
                if '"Edit"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Edit":
                        continue
                    inp = block.get("input") or {}
                    if inp.get("file_path") != file_path:
                        continue
                    total += payload_len(inp)
    except OSError:
        return 0
    return total


def main():
    payload = uc.hook_payload()
    if payload.get("tool_name") != "Edit":
        return
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    transcript_path = payload.get("transcript_path")
    if not file_path or not transcript_path:
        return

    try:
        size = os.path.getsize(file_path)
    except OSError:
        return

    total = prior_payload(transcript_path, file_path) + payload_len(tool_input)
    if total <= size:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                f"This session's `Edit` calls on {file_path} now total {total:,} chars of "
                f"old_string+new_string, more than the file's own {size:,} bytes — every one of "
                "them stays in context for every request after it. Consider Write-ing the whole "
                "file once instead of continuing to Edit it piecemeal."
            ),
        }
    }))


try:
    main()
except Exception:  # a bug here must never be able to block a tool call
    sys.exit(0)
