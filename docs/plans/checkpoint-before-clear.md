# Recognize the cheap moment to checkpoint and clear, and verify it actually happened

Cache-read is ~98% of a window's tokens (`usage/notes.md`), and continuing a session keeps
re-paying for everything already in its context. Two separate things make a moment cheap to
interrupt for a `/clear`:

1. **Continuing is about to get expensive anyway.** The prompt-cache TTL is bracketed at 54–141
   minutes (`usage/notes.md`). Once a session has sat idle longer than that, its *next* request
   pays a full cache rewrite — roughly the size of its entire context, at cache-write price — to
   re-establish what a cache-read would otherwise have covered for a fraction of the cost. Clearing
   right then costs nothing extra: the alternative was already about to be expensive.
2. **The floor is cheap next to what's accumulated**, even with a warm cache. A fresh session pays
   a ~22.1K floor (`docs/plans/per-request-cost.md`) before doing any work. Once a session's
   context is a large multiple of that, re-paying the floor is cheap next to one more request at
   the current size — this catches a session that has simply grown large while staying
   continuously active, which the TTL trigger above never sees.

`docs/plans/carried-context-gate.md` targeted a third, different moment — crossing the 5-hour
credit-window boundary — reasoning it was "the moment with the most requests still ahead of it" and
detectable for free. That conflated two unrelated mechanisms: the credit window is a wall-clock
rate-limit accounting boundary; the prompt cache's TTL is a separate, much shorter one. A session
can cross a window boundary on a warm cache (requests every few minutes, never idle long enough to
matter), or blow the TTL repeatedly without ever crossing a boundary — crossing a 5-hour window
*without* at least one 54+ minute gap somewhere in it is the unusual case, not the norm.

That plan's own Phase 1 — measure the carried-in-size distribution before setting a threshold — was
never done, so the window-boundary framing was never checked against data. The one dataset that
exists, `usage/events.jsonl`, argues against it directly: every `carried-context` firing so far (3,
all in one window) coincided with the same ~140-minute idle stretch that also produced a full cache
rewrite in each of those sessions (`usage/notes.md`). There is no recorded instance of a large
context surviving a window boundary on a warm cache. The mechanism the log actually caught was the
TTL crossing; the window boundary was only ever a coincidental proxy for it, and — because the TTL
is far shorter than the window — a proxy that misses most TTL crossings, since most of them don't
happen to land on a window boundary. **Retire the window-boundary trigger and gate on the TTL
crossing directly.**

## Phase 1 — trigger on the TTL crossing, not the window boundary

- [ ] In `hooks/usage_gate.py`, change `carried_reason()` (or its replacement) to fire on: time
      since the session's last request exceeds the TTL bracket, and its context
      (`session_carry()`'s `context`) is at or above a size threshold — not on `first <
      state["window_start"]`. Both inputs come from the session's own transcript; no window
      bookkeeping is needed at all.
      - Narrow the TTL bracket first if it's cheap to: 54–141 minutes is wide enough that a
        90-minute idle session is ambiguous. A few more bracketing observations recorded in
        `usage/notes.md` narrow it without changing the mechanism.
- [ ] Retire the `carried-context` event kind under its current (window-boundary) definition —
      every existing line in `usage/events.jsonl` describes a coincidence, not the mechanism. Log
      the new trigger under a new kind (e.g. `cache-expired`) so a future reader doesn't re-conflate
      the two the way this plan originally did.
- [ ] Set `CARRY_AT` in `hooks/usage_common.py` — still a guess, the comment says so — from a
      measured distribution of context sizes at real TTL-crossings, the same way
      `docs/plans/per-request-cost.md` measured the floor. Not from reasoning.

## Phase 2 — trigger on context size alone, independent of idle state

- [ ] Confirm what a `Stop` hook can see and do: whether it can read the current context size the
      way `session_carry()` already does, and whether it can block the turn from ending — inject
      `additionalContext` and force another turn — the way `PreToolUse` can deny a call.
- [ ] Pick the size threshold from observed firing frequency, not from the ratio alone. A threshold
      derived only by reasoning ("context is clearly bigger than the floor") is a guess
      (`rules/measure-before-recording.md`) and would be true almost immediately, nagging on nearly
      every turn. Run a candidate for a session or two and record in `usage/notes.md` how often it
      fired against how often the context had actually grown enough to matter.

## Phase 3 — broaden what "safe to clear" checks, beyond one repo's git status

Everything that must survive a `/clear` is whatever exists only in this conversation — not just
uncommitted files. Three kinds, and only the first is mechanically checkable:

- [ ] `git status --porcelain` in every repo touched this session. Useful because a clean tree pins
      the record to a specific commit, but treat it as **corroborating, not required** — work can
      be durable (a memory written, a rule landed elsewhere) without this repo's tree being clean,
      and a clean tree doesn't prove nothing was missed.
- [ ] Instructions the user gave this session for handling a situation that generalizes beyond the
      current project. If the session is in some other repo and the user told the agent how to
      handle something that applies everywhere, that belongs in a rule or skill **in this repo**
      (`global-claude-rules`), not left to be re-explained next time. The hook cannot write this
      itself — it can only ask the agent to check, and if something generalizable was never written
      down, name it in the nudge so the user can have a separate agent pick it up.
- [ ] Anything meeting this project's own memory criteria (the `user` / `feedback` / `project` /
      `reference` types) that was learned this session and never saved.

The hook's message asks the agent to work through these three before telling the user it's safe to
clear — one firing asks for the recording, a later firing confirms it landed, never both claims at
once.

## Success criteria

- The Phase 1 trigger fires on idle-gap-past-TTL sessions regardless of where the credit window
  happens to be, and never fires merely for crossing a window boundary.
- The Phase 2 trigger fires on a session that never wrote a plan file and never went idle, once its
  context crosses the measured threshold.
- No firing tells the user it's safe to `/clear` while something identifiably durable-but-unsaved is
  still only in the conversation — an uncommitted file, an unwritten cross-project rule, or an
  unsaved memory the agent itself would judge worth saving.

## Out of scope

- Automatically clearing or compacting. A hook cannot invoke either, and a wrapper that restarts a
  session behind the user's back would lose work the transcript does not capture.
- Reducing request count. A separate lever on the same total, not measured here.
