#!/usr/bin/env python3
"""Whether the shared credit window still has room, checked from the shell.

    python3 usage/check-gate.py

Prints the estimated percentage of the window spent and exits 0 if that
estimate is still under GATE_AT_PCT, 1 if it is at or past it. Same question
hooks/usage_gate.py answers on every prompt, but callable directly — no hook
payload, no session to tag, for a script or a loop to check before doing more
work rather than finding out by being refused mid-turn.

Needs to know when the current window began. The most direct evidence is a
reported renewal still in the future, then the last `renewed` boundary line in
events.jsonl; a session writes that line when it notices the log doesn't
already say so (see window_state() in hooks/usage_common.py), but nothing
guarantees one exists — a window can turn over with nobody around to record
it. Rather than reconstructing a lapsed boundary by rolling forward through
every transcript, this settles for the cheap answer: past one full window
since the newest such evidence, usage is treated as 0% and the check passes.

Once a window start is in hand, transcripts give the tokens spent since it —
scan_transcripts() reads every request's usage, exactly as the live hooks do.
Converting that to a percentage is the other half, and it does not wait for
this window's own usage-report readings to calibrate a fresh slope: it applies
the relationship already measured across past windows (usage/notes.md),
because requiring live readings is what would make this "unknown" in the
common case where nobody has reported one yet.
"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
os.environ.setdefault("REPO_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import usage_common as uc  # noqa: E402

# pct = PCT_INTERCEPT + tokens / TOKENS_PER_PCT. Best fit so far (usage/notes.md,
# "% used maps linearly to tokens, with a nonzero intercept"): one window, 6
# readings spanning 15.5M-46.9M tokens, every reading within 2.3pp of the fit.
TOKENS_PER_PCT = float(os.environ.get("CLAUDE_TOKENS_PER_PCT", "1267529"))
PCT_INTERCEPT = float(os.environ.get("CLAUDE_PCT_INTERCEPT", "17.3"))


def find_recent_renewal(events):
    """Start of the current window, from direct evidence only — never by
    rolling forward through transcripts to reconstruct one that already lapsed.
    None when the newest evidence is already a window old.
    """
    for event in reversed(events):
        if event.get("kind") == "usage-report" and isinstance(event.get("renewsInMin"), (int, float)):
            candidate = event["_t"] + timedelta(minutes=event["renewsInMin"])
            if candidate > uc.now:
                return candidate - uc.WINDOW

    logged = uc.logged_window_start(events)
    if logged is not None and uc.now - logged < uc.WINDOW:
        return logged
    return None


def main():
    events = uc.read_events()
    window_start = find_recent_renewal(events)

    if window_start is None:
        print("current ~0% used — no renewal logged within the last window, treating it as fresh")
        return 0

    requests, _sessions = uc.scan_transcripts(window_start)
    spent = uc.tokens_through(requests)
    estimate = PCT_INTERCEPT + spent / TOKENS_PER_PCT
    exceeded = estimate >= uc.GATE_AT_PCT
    print(
        f"current ~{min(estimate, 100):.0f}% used ({spent:,} tokens since the last renewal at "
        f"{uc.stamp(window_start)}, {TOKENS_PER_PCT:,.0f} tokens/% + {PCT_INTERCEPT:.1f} intercept) "
        f"— gate at {uc.GATE_AT_PCT:.0f}%"
    )
    return 1 if exceeded else 0


if __name__ == "__main__":
    sys.exit(main())
