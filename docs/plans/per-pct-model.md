# A better model for tokens-per-percent

`calibrate()` in `hooks/usage_common.py` fits `pct = intercept + tokens/per_pct` by whole-window
least squares. Checked against the three windows with a known true value (`final total / 100`, only
possible for a window confirmed run to exhaustion), the fit overshoots true `per_pct` by 13–51% —
see "Calibration: tokens-per-percent by window" in `usage/notes.md`. Two candidate causes (a
subagent-transcript scanning gap, external-client usage against the same account) are checked and
closed; what's left is shaped like a curve — per-reading `tokens/pct` rises through the middle of a
window and drops back down near the end — not like scattered noise, which a straight-line fit with a
free intercept absorbs into an offset instead of flagging as a bad fit.

- [ ] Build a local-slope model: predict from only the two most recent readings instead of a
  whole-window fit. Backtest with the same held-out method as "Within-window convergence" in
  `usage/notes.md` (fit on the first *k* readings, measure error against the rest) across windows
  A–D, and record the held-out error per window next to the existing `calibrate()` numbers.
- [ ] Build a cost-weighted least-squares fit: same `calibrate()` shape, but on token totals
  weighted by the list-price ratios already used this session (cache-write ×1.25, cache-read ×0.1,
  output ×5 — flagged there as a guess, not a measurement). Backtest the same way.
- [ ] For windows A, B, C — the ones with a true `per_pct` — score every candidate (current
  `calibrate()`, local-slope, cost-weighted) against that true value, not just against the fitted
  line's own residual.
- [ ] Record the full comparison in `usage/notes.md`: does any candidate beat the current model on
  *both* held-out error and true-value accuracy, in every window tested, or only some?
- [ ] If one candidate wins consistently, replace or augment `calibrate()` in
  `hooks/usage_common.py`, and update the `estimate ~X% used` line in `usage_report.py` and the
  gate math in `usage_gate.py` / `usage_tool_gate.py` to use it. Leave the existing single-reading
  guess path (fewer than 2 readings in a window) unchanged — there's nothing to fit yet either way.
- [ ] If no candidate wins consistently (mixed results across windows), leave `calibrate()` as-is
  and record why in `usage/notes.md` instead of forcing an adoption.

## Out of scope

- The other open questions already tracked in `usage/notes.md`'s "Still gathering data on" table
  (the `CARRY_AT` and `CHECKPOINT_AT` knees, `MARGIN_CALLS`) — those need a natural event to occur,
  not a model change, and are already tracked there.

## Success criteria

- `usage/notes.md` states, for windows A–D, whether a better model than the current `calibrate()`
  was found, with the held-out and true-value numbers backing that conclusion either way.
