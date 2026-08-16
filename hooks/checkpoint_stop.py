#!/usr/bin/env python3
"""Nudge a checkpoint when context is large and the session never went idle.

Registered by install-hooks.sh as a Stop hook. usage_gate.py's
carried_reason (UserPromptSubmit) only catches a session once it goes idle past
the prompt-cache TTL; a session that stays continuously active never reaches
that gate no matter how large its context grows. This is the complementary
trigger: context size alone, checked at the end of every turn.

Fires at most once per session: logging a `checkpoint-nudged` event is what
stops it asking again. Nothing else would — a Stop hook has no documented
equivalent of `stop_hook_active` to break a loop on its own, and blocking a
stop forces another turn whose own request only adds to the context this hook
is reacting to.

CHECKPOINT_AT was originally set equal to CARRY_AT (usage_common.py) as a
placeholder, not a measurement: CARRY_AT was picked for a session that has
already gone idle, and this trigger fires on one that never does, so nothing
confirmed the two belonged at the same number. Every real firing so far
landed at 71,675-113,950 tokens and was accepted (a `cleared` event followed
within minutes), which says nudging works in that range but nothing about
whether 50,000 was the right place to start — there was no data below it.
CHECKPOINT_AT is now set to 35,000 instead: still a guess, not a measurement,
chosen to sit above this repo's measured ~30,000-token floor (so it doesn't
fire before any real work happens) while being low enough to bracket the
missing range. What would confirm or replace this guess is the next batch of
`checkpoint-nudged` events landing lower than the old range: if they're still
followed by a quick `cleared`, the threshold can drop further; if a nudge
starts going unanswered, that's the knee. `checkpoint-nudged` does not log the
context size itself — it's redundant, recoverable after the fact from the
transcript at whatever threshold turns out to be worth asking about. What it
logs instead is the one fact a transcript can't reconstruct: that the hook
fired here at all. A later `cleared` event (usage_report.py, logged when a
session's SessionStart fires with source `clear`) links back to whichever
nudge preceded it by `claude_pid`, which is what judging a threshold by its
actual outcome — not just how often it fires — needs.

Never fails a turn: any error exits 0 with no output.
"""

import json
import os
import sys

import usage_common as uc

CHECKPOINT_AT = int(os.environ.get("CLAUDE_CHECKPOINT_CONTEXT_TOKENS", "35000"))

MESSAGE = (
    "Context just crossed {tokens:,} tokens with no idle gap to prompt a checkpoint on its own. "
    "Before doing anything else: check `git status` in every repo touched this session, not just "
    "the working directory; and write down anything learned this session that would otherwise "
    "be re-explained next time — as a rule, that project's CLAUDE.md, or a plan file under "
    f"{os.path.join(uc.REPO_DIR, 'docs/plans')}, following the routing in "
    "`rules/no-memory-directory.md` (never into `~/.claude/projects/*/memory/`). Do all of "
    "this in as few tool calls as possible: context is at its largest right now, so every call "
    "costs more than it will again until the next /clear. Then tell the user plainly that this is "
    "a good moment to /clear or /compact."
)


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
    context, _weighted, _last, _first = carry
    if context < CHECKPOINT_AT:
        return

    events = uc.read_events()
    if already_nudged(events, session_id):
        return

    event = {"kind": "checkpoint-nudged"}
    pid = uc.claude_pid()
    if pid:
        event["claude_pid"] = pid
    uc.append_event(session_id, event)
    print(json.dumps({"decision": "block", "reason": MESSAGE.format(tokens=context)}))


try:
    main()
except Exception:  # a bug here must never be able to trap a turn from ending
    sys.exit(0)
