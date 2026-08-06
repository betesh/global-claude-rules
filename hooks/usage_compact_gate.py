#!/usr/bin/env python3
"""Decide whether a /compact is worth starting, before it runs.

Invoked by usage-compact-gate.sh with REPO_DIR set, on every PreCompact
(manual or automatic). A compact reaches the API like any other request and
can spend real tokens even when it fails (usage/notes.md: a failed one spent
~4 minutes ingesting ~434K tokens before a 529), so a window that's nearly out
of credit is a bad moment to start one. Reuses the same threshold as
usage_gate.py's prompt gate (usage_common.gate_reason).

Exit codes are the whole interface:

  2  credit is gone; the harness cancels the compact and shows our stderr
  0  let it run

Only a deliberate 2 blocks. Any other failure — a crash, a missing python, a
malformed log — exits 0, because a bug in accounting must never be able to
stop a compact that's actually needed.
"""

import argparse
import sys

import usage_common as uc


def parse_args():
    parser = argparse.ArgumentParser(description="Gate a /compact on the shared credit window.")
    parser.add_argument("--session", help="session id to tag anything this run appends to the log")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = uc.hook_payload()
    session_id = args.session or payload.get("session_id") or None
    trigger = payload.get("trigger") or "unknown"

    events = uc.read_events()
    state = uc.window_state(events)
    if state["unlogged"]:
        uc.log_boundary(session_id, state["window_start"])

    reason = uc.gate_reason(state)
    if reason:
        why, until = reason
        print(
            f"Credit is out: {why}. Refusing to start this {trigger} compact — it can spend real "
            "tokens, or fail after already spending them, for a window that's about to end anyway. "
            f"The window renews at {uc.stamp(until)}, {uc.duration(until - uc.now)} from now — wait "
            "until then, or set CLAUDE_USAGE_GATE_PCT above the current estimate to override.",
            file=sys.stderr,
        )
        sys.exit(2)


try:
    main()
except Exception:  # a bug here must never be able to block a compact that's actually needed
    sys.exit(0)
