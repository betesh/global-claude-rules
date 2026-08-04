---
name: render-before-concluding
description: Generate a handful of different renderings/transformations of an ambiguous visual or spatial region before concluding what it shows, instead of resolving it from algorithmic proxies or a single rendering alone. Load this whenever an agent has to analyze, classify, or debug something visual — images, pixel data, shapes, spatial layout — and the answer is genuinely ambiguous. Triggers on "OCR", "ink blob", "which letter/shape is this", "image looks like", "why is this pixel/region", "visual bug", "orientation bug", "fused/overlapping shapes", "classify this region", "algorithmic heuristic disagrees".
---

# Render before concluding

_When a visual or spatial question is ambiguous, generate several different renderings of the
region before deciding — not just one, and not purely from algorithmic proxies._

An algorithmic proxy — a width ratio, a variance score, an oracle count deficit — collapses a
region to a single number. When that number disagrees with reality, the proxy isn't a stand-in for
looking; it's an assumption that skipped the step where a person or model actually sees the thing.
Observed twice, in unrelated repos: an agent decided ink blobs were fused letters using proxies
that were actively misleading, and a plan document blamed a mis-orientation bug on a "ruled"
surface based on four proxies that all failed to separate the hypothesis from reality. In both
cases, rendering the actual region resolved it immediately, and in a way none of the proxies had
captured — the proxies were wrong in shape, not just in magnitude.

## What to do

Before concluding on an ambiguous visual/shape/spatial question, generate several different
renderings of the same region, for example:

- the raw crop
- a mask or overlay isolating the feature in question
- a derived heatmap (distance transform, density profile, etc.)
- a contrast-stretched or channel-isolated version
- a candidate hypothesis drawn directly onto the actual pixels (e.g. overlay a candidate line-band
  on the real ink mask) rather than only described in text

Look at the renders — or show them to the user — before trusting a proxy score that disagrees with
what they show.

## Say what's confirmed versus guessed

State plainly whether an identification is a heuristic guess or something actually confirmed by
looking at a render. Don't present a proxy-derived conclusion with the same confidence as one that
was directly observed.

## Scope

Not a specialist "image agent" skill. Ordinary software debugging qualifies too, whenever the bug
is spatial or visual in nature (layout, alignment, rendering, orientation) and text-only proxies
keep disagreeing with each other or with the observed behavior.
