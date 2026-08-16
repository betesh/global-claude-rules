---
name: repo-plans
description: Rules for living implementation plans in docs/plans/. Load this BEFORE writing a plan file, immediately after the user approves a plan in ExitPlanMode, before committing work that advances a plan, when trimming or finishing a plan, or when adding to DEFERRED.md. Triggers on "write a plan", "implement the plan", "the plan file", "docs/plans", "next phase", "deferred backlog".
---

# Living plans in docs/plans

_The plan file lives in the owning repo, shrinks to remaining work every commit, and is deleted
when done._

## Where plans live

Active plans go in the **owning repo's** `docs/plans/<name>.md` — the repo where the first phase
lands. Write the file with Write/Edit; the text shown in `ExitPlanMode` is conversation state and
disappears on compaction. Never leave the only copy in the scratchpad, a task entry, or chat.

Plan mode is read-only, so **the first action after approval is writing the plan file** — not the
first code edit. If the work is too small to warrant one, say so deliberately rather than silently
skipping it. Editing an existing plan is not planning and does not need plan mode.

For a large multi-phase plan, writing the file is a pause point, not a formality to rush past —
give the user a chance to read the written plan before starting the first implementation step,
even though the plan was already approved in conversation. A small plan doesn't need this pause.

## Structure

Phases with `- [ ]` checklist items for remaining work. Put constraints, paths, algorithms, and
tests **under the item they apply to**, not in a preamble. A short shared diagram or glossary at
the top is fine.

Do **not** add **Decisions**, **Background**, or similar sections restating settled choices —
encode a decision as a constraint under the item it affects, or as a non-goal under **Out of
scope**. Git history covers "why we chose X".

Three end-of-plan lists are allowed for genuinely cross-cutting items: **Success criteria**
(whole-plan gates), **Out of scope** (non-goals and rejected approaches), **Deferred** (later work
we still intend to do). Prefer putting a criterion under its own item.

## Keep only remaining work

**One git commit per completed phase** (or per top-level item when phases are thin). In that same
commit, **delete** the finished items and their nested detail from the plan file.

`- [x]` is never a valid plan update. Neither is strike-through, "done", "completed in …", or a
"Shipped" section. Remove the item entirely and drop the empty heading. Before committing
plan-advancing work, grep the staged plan for `- [x]` and delete anything left.

Finishing an item without shrinking the plan in that commit is a rule violation. Do not batch
several phases into one commit, and do not defer the plan edit to a follow-up. The session todo
list is not a substitute: todos track this turn, the plan tracks the work.

## When trimming, sort what was nested under it

| kind | where it goes |
|---|---|
| Later work we still intend to do | plan's **Deferred**, or `DEFERRED.md` |
| Non-goal or rejected approach | plan's **Out of scope**, or a standing rule — never `DEFERRED.md` |

Prefer promoting into the end-of-plan list while the plan is active. Never drop a nested note
silently.

## Finishing

When the last in-scope item lands, that same commit moves any still-relevant **Deferred** bullets
to `DEFERRED.md` at the repo root (or the repo's existing equivalent) and **deletes the plan file**.
No empty stubs, no "completed plan" archives.

`DEFERRED.md` is a **pickup list of actionable future tasks** — nothing else. Before adding a
bullet, read the list: if the work fits an existing one, broaden that bullet instead of adding a
near-duplicate. Keep out permanent non-goals, finished success criteria, anything already a `- [ ]`
in an active plan, policy already covered by a standing rule, and all history or provenance
("from plan X", "moved from Phase A") — git history is enough. If you would not open a plan whose
next item is that bullet, it does not belong there. Do not create an empty `DEFERRED.md`.

Nothing outside a plan may cite it — no phase numbers or plan paths in code, docs, or test names.
Do not restate any of this housekeeping inside a plan document.
