# Stop sessions from carrying context across a window boundary

Cache-read is 97–98% of every window, and `total ≈ requests × average context`. The largest single
term in that average is history a session already held before the window opened — larger than tool
calls, tool results and replies together. How much larger is what Phase 1 measures; the ordering is
what makes it the lever worth building on.

The saving is entirely a matter of *when* a session is cleared. Clearing a session holding a
hundred thousand tokens that then runs a hundred more requests saves millions of tokens; clearing at
an arbitrary moment saves almost nothing. The one moment with the most requests still ahead of it is the window boundary — and
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

## Phase 2 — set the threshold from the measurement

- [ ] Replace the `CARRY_AT` guess in `usage_window.py` with the figure Phase 1 measures, and drop
      the comment marking it provisional.

## Phase 3 — confirm it saved what it claimed

- [ ] Over the first two window boundaries the gate is live for, record in `usage/notes.md`: how
      often it fired, how often the user cleared versus overrode, and the window's carried-in share
      against the baseline Phase 1 recorded.
      - A drop in carried-in share that does not show up as fewer tokens per percent means the
        saving went into more requests instead; say so rather than claiming the win.

## Success criteria

- Carried-in context, measured by the per-session view, is a smaller share of window cache-read
  than the baseline Phase 1 records, over at least two boundaries.
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
