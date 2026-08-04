# Cut what every request pays before it does any work

`total ≈ requests × average context`, and three terms in that product are addressable separately:
the floor every request pays before any conversation exists, the number of requests a turn spends,
and the payloads that edits leave behind. Measured over one window (140 requests, 10.5M tokens):
the floor was 22.1K per request (35% of what the attribution can see), requests producing under 400
output tokens were 44% of all requests and 43% of context spend, and `Edit` inputs carried 746K.

## Phase 2 — find what the floor is actually made of, and whether any of it is ours

The floor was 21,905 / 22,109 / 22,166 / 22,188 tokens across four sessions — stable enough that a
difference of a thousand tokens between two configurations is a real signal. `permissions.deny` on
deferred tools, the session-start rule load, and cache-hit/miss visibility are answered — see
`usage/notes.md`; none of them move the floor enough to act on, and cache-hit/miss is already
exposed per request.

- [ ] Measure the floor per configuration **interactively**, not scripted: a scripted `claude -p`
      run's floor (29,205–29,213, three runs, this repo's dir) sits ~7,000 tokens above the
      21,905–22,188 interactive baseline above, so absolute numbers from `-p` don't transfer — see
      `usage/notes.md`. Vary one thing at a time (empty directory, hooks alone, each candidate) and
      record every number with its configuration in `usage/notes.md`.
      - Isolating hooks alone is still open: `--settings '{"hooks":{}}'` does not override
        `~/.claude/settings.json`'s `hooks` key (the SessionStart hook still fired, confirmed via a
        `-d api` debug log), and `--setting-sources project,local` came back polluted by a partial
        cross-session cache hit. Find a way to disable only hooks, or accept that this needs a
        human-attended interactive session rather than a scripted one.

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
