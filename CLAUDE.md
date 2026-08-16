# Working in this repo

This repository holds the global rules loaded into every Claude Code session on this machine.
Everything below applies **only when you are working here**, which is why it lives in this file
rather than in `rules/` — anything in `rules/` is re-read on every request of every session, in
every project.

## This is a repo like any other

Edits to these rules follow the same workflows as any other repository, including **auto-commit**.
Ending a turn with intentional uncommitted changes here is a violation, even when the session's
working directory is a different project — use `git -C <this-repo>` for status, add, and commit.

Do not skip committing rule edits because they sit outside the working directory.

## Adding or changing a rule

- One concern per file, in `rules/`, as `.md`. The filename is the rule's identifier; other rules
  cite it by filename.
- Nothing outside `rules/` is loaded. `README.md`, `install-hooks.sh`, `hooks/`, and this file are
  project files — do not write behavioral instructions into them expecting to be bound.
- **Every file in `rules/` is re-read on every request of every session.** Measured at roughly
  **0.4 points of a credit window per 1,000 tokens**, more when several agents run. Adding a rule
  is a recurring cost paid by every agent at once, so say it once, in the shortest form that binds,
  and prefer deleting text to adding it.
- Before adding one, check whether it can be enforced instead of stated: a hook that blocks the
  mistake costs no context at all, and a rule that only applies in one repo belongs in that repo.

## Keep the rules project-agnostic

These load in every repo, so they must read sensibly in every repo.

- Use generic terms: the repo, the plan file, the package, tests, docs. Illustrate with vocabulary
  every programmer has — files, requests, retries, caches, timeouts.
- Put project-specific names, paths, fixtures, and product vocabulary in **that** repo's own
  `CLAUDE.md` or `.claude/rules/`.
- Do not encode facts that go stale: version numbers, someone's current branch, a URL that moves.
- **Do not explain a rule in one project's domain vocabulary.** An example whose nouns, units, or
  thresholds only mean something once you know a particular problem domain is as repo-specific as
  one naming the product, and reads as noise everywhere else.

Read your example as someone working in an unrelated codebase — a payments API, a game engine, a
CLI. If they cannot tell what it demonstrates without asking what its terms mean, rewrite it;
renaming identifiers is not enough when the whole scenario is domain-bound. The usual source of a
leak is the code you were working in when the rule occurred to you.

## Usage instrumentation

`usage/events.jsonl` (gitignored) and `usage/notes.md` (committed) track what is known about the
shared credit window; `hooks/usage_common.py` computes it, for `hooks/usage_report.py` and
`hooks/usage_gate.py`. See `rules/usage-limits-and-context.md`
for what to log. Conclusions belong in `notes.md` as a description of what we know — not a dated
log of when each thing was learned.

### Keeping `notes.md` current

- State current knowledge only, not the investigation that produced it. Superseded numbers, fixed
  bugs, and corrected reports belong in git history and commit messages, not in the file. A
  ruled-out cause for a still-open question is worth keeping, but trim it to the method and metric
  that ruled it out, not the narrative around it.
- Every per-window table stays sorted chronologically by window, even when the table's point is to
  compare values across windows — insert a new window's row in order, and make any value-ordering
  claim in the prose next to the table rather than by reordering rows.
- When re-running or re-writing numbers derived from `usage/events.jsonl`, check whether additional
  windows have renewed since the file was last updated, not only the window that was asked about —
  list `renewed` events and compare against what's already in the tables.

## Verify a rule's or plan's stated rationale

Before defending, keeping, or restating why a rule in `rules/` or a mechanism in `hooks/` exists,
trace its actual consumers in code rather than repeating the rule's own prose justification — grep
`hooks/*.py` for what actually reads a given field or event kind. If nothing consumes it, say so
and remove it rather than patching the rationale. The same applies to a plan's stated reasoning for
why a moment or threshold matters: check it against `usage/events.jsonl` / `usage/notes.md` before
carrying it forward, rather than accepting the plan's own intro prose as settled.
