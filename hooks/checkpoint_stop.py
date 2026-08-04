#!/usr/bin/env python3
"""Nudge a checkpoint when context is large and the session never went idle.

Registered by install-hooks.sh as a Stop hook. usage_gate.py's
carried_reason (UserPromptSubmit) only catches a session once it goes idle past
the prompt-cache TTL; a session that stays continuously active never reaches
that gate no matter how large its context grows. This is the complementary
trigger: context size alone, checked at the end of every turn.

Skipped when a plan file was already written this session — plan-written.py's
PostToolUse hook already delivered the same nudge at the moment the plan itself
became durable, and firing this one too would ask for the same save twice.

Fires at most once per session: logging a `checkpoint-nudged` event is what
stops it asking again. Nothing else would — a Stop hook has no documented
equivalent of `stop_hook_active` to break a loop on its own, and blocking a
stop forces another turn whose own request only adds to the context this hook
is reacting to.

CHECKPOINT_AT starts equal to CARRY_AT (usage_common.py) as a placeholder, not
a measurement: CARRY_AT was picked for a session that has already gone idle,
and this trigger fires on one that never does, so nothing yet confirms the two
belong at the same number. Firing logs the context size alongside
`checkpoint-nudged`, which is what a future pass needs to pick this threshold
from observed frequency instead of the borrowed ratio
(docs/plans/checkpoint-before-clear.md).

Never fails a turn: any error exits 0 with no output.
"""

import json
import os
import sys

import usage_common as uc

CHECKPOINT_AT = int(os.environ.get("CLAUDE_CHECKPOINT_CONTEXT_TOKENS", str(uc.CARRY_AT)))

MESSAGE = (
    "Context just crossed {tokens:,} tokens with no idle gap to prompt a checkpoint on its own. "
    "Before doing anything else: check `git status` in every repo touched this session, not just "
    "the working directory; save anything meeting this project's own memory criteria that was "
    "learned this session and never written down; and write down any instruction the user gave "
    "that generalizes beyond this project — as a memory, in "
    f"{uc.CONFIG_DIR}/projects/<project>/memory/MEMORY.md, or as a plan under "
    f"{os.path.join(uc.REPO_DIR, 'docs/plans')} when it isn't specific to this project. Do all of "
    "this in as few tool calls as possible: context is at its largest right now, so every call "
    "costs more than it will again until the next /clear. Then tell the user plainly that this is "
    "a good moment to /clear or /compact."
)


def plan_file_written(transcript):
    """Whether this transcript already contains a Write to docs/plans/*.

    Mirrors the path check in plan-written.py, which fires on that same event.
    """
    try:
        with open(transcript, errors="replace") as f:
            for line in f:
                if '"name":"Write"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for block in (entry.get("message") or {}).get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Write":
                        continue
                    path = (block.get("input") or {}).get("file_path") or ""
                    parts = os.path.normpath(path).split(os.sep)
                    if "docs" in parts and parts.index("docs") + 1 < len(parts) \
                            and parts[parts.index("docs") + 1] == "plans":
                        return True
    except OSError:
        pass
    return False


def already_nudged(events, session_id):
    return any(
        e.get("kind") == "checkpoint-nudged" and e.get("session") == session_id
        for e in events
    )


def main():
    payload = uc.hook_payload()
    session_id = payload.get("session_id")
    transcript = payload.get("transcript_path")
    if not session_id or not transcript:
        return

    carry = uc.session_carry(transcript)
    if not carry:
        return
    context, _last, _first = carry
    if context < CHECKPOINT_AT:
        return

    events = uc.read_events()
    if already_nudged(events, session_id) or plan_file_written(transcript):
        return

    uc.append_event(session_id, {"kind": "checkpoint-nudged", "context": context})
    print(json.dumps({"decision": "block", "reason": MESSAGE.format(tokens=context)}))


try:
    main()
except Exception:  # a bug here must never be able to trap a turn from ending
    sys.exit(0)
