# Cut what every request pays before it does any work

`total ≈ requests × average context`, and three terms in that product are addressable separately:
the floor every request pays before any conversation exists, the number of requests a turn spends,
and the payloads that edits leave behind. Measured over one window (140 requests, 10.5M tokens):
the floor was 22.1K per request (~30% of the window), requests producing under 400 output tokens
were 44% of all requests and 43% of context spend, and `Edit` inputs carried 746K.

Phase 1 is a prerequisite for the other two: the attribution tool does not yet account for most of
a window, so any figure the later phases quote from it would be wrong in the same direction.

## Phase 1 — make the attribution honest before reading anything off it

- [ ] Account for thinking, which occupies context but is not recoverable from the transcript.
      - Transcripts persist `signature` and an empty `thinking` string, so `blocks()` scores it
        zero; one measured session emitted 65.7K output tokens against ~21K of text and tool calls.
      - Derive it per request as output tokens minus the text and tool-call tokens on that same
        request, and label the row as derived, not measured, wherever it prints.
- [ ] Re-run over a full window and record the accounted-for percentage in `usage/notes.md`.
      - It is 45% today. If the two fixes above do not take it near the measured cache-read, the
        remainder is a fourth term nobody has named yet; say that rather than rounding it away.

## Phase 2 — find what the floor is actually made of, and whether any of it is ours

The floor was 22,111 / 21,907 / 22,190 tokens across three sessions — stable enough that a
difference of a thousand tokens between two configurations is a real signal.

- [ ] Measure the floor per configuration by reading the first request's context out of the
      transcript it writes, one short prompt per run.
      - Vary one thing at a time from the current setup: an empty directory (no project
        `CLAUDE.md`), hooks disabled, and each candidate below. Record every number with the
        configuration beside it in `usage/notes.md`.
      - Confirm first that a scripted run's floor matches the interactive figures above. If it does
        not, the harness sends a different preamble for it and every delta measured this way is
        against a different baseline — say so and measure interactively instead.
- [ ] Establish whether deferred tool schemas can be dropped, which is the largest candidate:
      `/context` attributed 16.7K to them against 10.3K for the always-loaded tools.
      - `permissions.deny` is the only lever in reach; whether denying a tool removes its schema
        from the preamble or merely blocks the call is exactly what the measurement answers.
      - If the floor does not move, record that the preamble is not adjustable from settings and
        stop — the remaining items in this phase are then dead too.
- [ ] Measure what the session-start rule load costs as delivered, against the same text supplied
      directly as context by the hook.
      - Today it is an instruction to read six files: one round trip, plus six tool calls and six
        results framing ~3K of rule text that then sits in context for the rest of the session.
      - Only pursue this if Phase 1's accounting shows the framing is a meaningful share. The rule
        text itself is not in scope here.

## Phase 3 — establish how much of the request count is avoidable

62 of 140 requests produced under 400 output tokens and cost 4.6M between them. That is what those
requests cost, not what removing them would save — the saving is only over the ones that did not
need to be their own request.

- [ ] Classify the low-output requests in one window's transcripts by what made each one separate:
      independent calls that could have been issued together, dependent shell steps that could have
      been one command, verification after an edit, and text between tool calls.
      - Report a token figure per class, ranked. Anything not clearly avoidable stays out of the
        total.
- [ ] Decide from that ranking whether the top class earns a standing rule, and record the decision
      in `usage/notes.md` either way.
      - A rule costs ~0.4 points of a window per 1,000 tokens, forever, in every session. If the
        top class is worth less than a few points, writing it down is a net loss and the finding is
        that the request count is already near its floor.
      - Prefer a hook that makes the pattern impossible over text that asks for it.

## Phase 4 — stop repeated edits to one file from accumulating

`Edit` inputs cost 746K in one window, 645K of it in a single session, because every `old_string`
and `new_string` stays in context for every request that follows it.

- [ ] Measure, per file per session, the number of edits and the total edit payload against the
      file's own size.
      - The case worth acting on is a file edited enough times that the payloads exceed rewriting
        it once. If no file in a measured window reaches that, say so and close the phase.
- [ ] If they do, add a `PreToolUse` hook on `Edit` that counts edits per file per session and
      warns past the measured crossover.
      - The count and the threshold live in the hook, which costs no context, rather than in a
        rule that every session pays for.

## Success criteria

- Tokens per percent of window improves against the figure recorded before the change, over at
  least two windows — the same measure used for any other saving here, so that a change that only
  moves spend between terms cannot look like a win.
- The attribution tool accounts for a stated share of measured cache-read, and no row in it is a
  guess presented as a measurement.

## Out of scope

- **Trimming tool output.** Measured under 0.1% of a window.
- **Shrinking `rules/`.** ~3,000 tokens total; already governed by `CLAUDE.md`, and an order of
  magnitude below the floor it sits inside.
- **The system prompt and always-loaded tool schemas.** Not adjustable from this machine; measuring
  them is worthwhile only to size what is left.
