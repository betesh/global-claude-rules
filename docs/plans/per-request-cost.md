# Cut what every request pays before it does any work

`total ≈ requests × average context`, and three terms in that product are addressable separately:
the floor every request pays before any conversation exists, the number of requests a turn spends,
and the payloads that edits leave behind. Measured over one window (140 requests, 10.5M tokens):
the floor was 22.1K per request (35% of what the attribution can see), requests producing under 400
output tokens were 44% of all requests and 43% of context spend, and `Edit` inputs carried 746K.

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
