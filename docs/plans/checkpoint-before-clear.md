# Recognize the cheap moment to checkpoint and clear, and verify it actually happened

## Phase 1 — set CARRY_AT from measured data, not reasoning

- [ ] `CARRY_AT` (`hooks/usage_common.py`) is still a guess. Real TTL crossings measured so far
      (two, read directly from transcripts) carried 231,467 and 71,903 tokens — both comfortably
      above the current 50,000 default, so it isn't contradicted, but two points can't locate the
      knee below which clearing saves less than the interruption costs. Extend the distribution
      with `usage/context-cost.py` over more real TTL crossings as they occur (`usage/notes.md`),
      and move the default to wherever the knee actually falls.

## Phase 2 — trigger on context size alone, independent of idle state

- [ ] Confirm what a `Stop` hook can see and do: whether it can read the current context size the
      way `session_carry()` already does, and whether it can block the turn from ending — inject
      `additionalContext` and force another turn — the way `PreToolUse` can deny a call.
- [ ] Pick the size threshold from observed firing frequency, not from the ratio alone. A threshold
      derived only by reasoning ("context is clearly bigger than the floor") is a guess
      (`rules/measure-before-recording.md`) and would be true almost immediately, nagging on nearly
      every turn. Run a candidate for a session or two and record in `usage/notes.md` how often it
      fired against how often the context had actually grown enough to matter.

## Success criteria

- The idle-gap trigger fires on sessions idle past the prompt-cache TTL regardless of where the
  credit window happens to be, and never fires merely for crossing a window boundary.
- A separate, context-size-only trigger fires on a session that never wrote a plan file and never
  went idle, once its context crosses the measured threshold.
- No firing tells the user it's safe to `/clear` while something identifiably durable-but-unsaved is
  still only in the conversation — an uncommitted file, an unwritten cross-project rule, or an
  unsaved memory the agent itself would judge worth saving.

## Out of scope

- Automatically clearing or compacting. A hook cannot invoke either, and a wrapper that restarts a
  session behind the user's back would lose work the transcript does not capture.
- Reducing request count. A separate lever on the same total, not measured here.
