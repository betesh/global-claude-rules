# Stop sessions from carrying context across a window boundary

Cache-read is 97–98% of every window, and `total ≈ requests × average context`. The largest single
term in that average is history a session already held before the window opened: measured at 59% of
all cache-read in one window, worth ~35 points, against ~9% for tool calls and ~8% for tool results.
Nothing else measured is close.

The saving is entirely a matter of *when* a session is cleared. Clearing a 250k-token session that
then runs a hundred more requests saves millions of tokens; clearing at an arbitrary moment saves
almost nothing. The one moment with the most requests still ahead of it is the window boundary — and
that is a moment a hook can detect for free, while nobody watching a session can.

So: refuse the first prompt a large session sends into a window it did not open, and say what
continuing will cost.

## Phase 1 — measure what carrying costs, per session

- [ ] Run the per-session view over a full window whose start the hook recorded itself, and record
      in `usage/notes.md`: the distribution of carried-in sizes, and how many points each cost.
      - This is what sets the gate's threshold. It must come from that run, not from reasoning —
        write it down with the window it was measured over beside it.
      - Wait for a window the hook dated. Earlier figures were measured against boundaries derived
        from readings since discarded as unreliable, so a run against one of those is not evidence
        and cannot be used to check this one.
      - What the view must satisfy, independent of any remembered figure: a session whose first
        request falls after the boundary reports zero however large it has grown, and the carried
        total never exceeds the window's measured cache-read.

## Phase 2 — gate the first prompt after a boundary

- [ ] Add a carried-context check to `usage_window.py --gate`, alongside the spent-window check.
      - Inputs, all already available: the hook payload's `session_id` and `transcript_path` on
        stdin, and the window start `window_state` computes.
      - Blocks when the session's first request predates the window start **and** its current
        context is at or above the Phase 1 threshold. Both conditions, or it fires on fresh
        sessions that merely grew large, where clearing saves nothing that was not just paid for.
      - Exit 2 with the cost on stderr: context size, requests this session has averaged per hour,
        and what that projects to as a share of the window if it continues. A number the user can
        weigh beats an instruction they cannot check.
      - Name both outs in the message: `/clear` when the next task does not depend on this
        conversation, `/compact` when the work must continue here.
- [ ] Make it a speed bump, not a lockout.
      - On blocking, append a `carried-context` event tagged with the session id. A session that
        already has one for this window is let through — re-submitting the prompt is the
        acknowledgement, so nobody can be locked out of their own session by a bad threshold.
      - `CLAUDE_CARRIED_CONTEXT_OK=1` skips the check entirely, for unattended runs that cannot
        answer a prompt.
      - The check must never block when the window start is one the log only guessed
        (`state["opened"]`), since then every session looks like it predates the window.
- [ ] Report carried context in the SessionStart block too, as one line, so a session that resumes
      into a fresh window sees the number before it is blocked by it.

## Phase 3 — confirm it saved what it claimed

- [ ] Over the first two window boundaries after Phase 2 lands, record in `usage/notes.md`: how
      often it fired, how often the user cleared versus overrode, and the window's carried-in share
      measured by the Phase 1 view against the 59% baseline.
      - A drop in carried-in share that does not show up as fewer tokens per percent means the
        saving went into more requests instead; say so rather than claiming the win.

## Success criteria

- Carried-in context, measured by the Phase 1 view, is a smaller share of window cache-read than
  the 59% baseline, over at least two boundaries.
- No session was ever prevented from continuing: every block was resolvable by re-submitting.

## Out of scope

- **Trimming tool output.** Measured under 0.1% of a window; the largest single tool result observed
  was 2,606 tokens.
- **Shrinking `rules/`.** All of it is ~3,000 tokens, roughly 1.2 points of a window at two
  concurrent sessions. Real, an order of magnitude below this, and already governed by CLAUDE.md.
- **Automatically clearing or compacting.** A hook cannot invoke either, and a wrapper that restarts
  a session behind the user's back would lose work the transcript does not capture.
- **Reducing request count.** A separate lever on the same product, and not measured yet.

## Deferred

- Per-model weighting in the fit. Weighting components by published price ratios fit better (worst
  residual 1.5 vs 2.1 points) but did not explain the spread; worth revisiting if readings ever
  arrive under a genuinely different traffic mix.
