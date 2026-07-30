# Living plans in docs/plans

_The plan file lives in the owning repo, shrinks to remaining work every commit, and is deleted when done._

## Where plans live

- Put **active** implementation plans in the **owning repo's** `docs/plans/` (markdown).
- **Write `docs/plans/<name>.md` directly** with the Write/Edit tools. The plan text you present in `ExitPlanMode` is ephemeral conversation state — it disappears on compaction and is **not** the artifact.
- Never leave the only copy of a plan in the session **scratchpad directory**, in a TaskCreate entry, or in chat. Those are working state; the plan file is the record.
- **Owning repo:** the repository where the first implementation phase lands. For multi-repo work, keep one living plan in that repo and describe later phases (including other repos) there until ownership clearly moves.
- Exception: if the plan **creates a new repository**, the plan may live outside that repo until the repo exists; then move it into that repo's `docs/plans/`.

## Plan mode

Plan mode is read-only — you cannot write the plan file while in it. So:

- Do the research and design in plan mode, and present the plan via `ExitPlanMode`.
- **The first action after the user approves is writing `docs/plans/<name>.md`.** Not the first code edit. A planning turn is incomplete until the plan file exists in the owning repo, and you do not wait for the user to ask for it.
- If the work is small enough that no plan file is warranted, say so and skip it deliberately — do not silently drop the plan.
- Iterating on an **existing** plan file is editing work, not planning: it does not require plan mode.

## Structure remaining work under checklist items

- Organize the plan as phases with checklist items for remaining work.
- Put constraints, file paths, algorithms, tests, and item-specific success bars **under the checklist item (or phase) they apply to**, not as a long narrative preamble outside the phases.
- Prefer nested bullets under `- [ ] **Item**` over separate background/decisions sections that duplicate the same content.
- A short shared diagram or glossary at the top is fine when several phases need it; do not dump phase-specific detail there.
- **Do not** add **Decisions**, **Already decided**, **Background**, or similar sections that restate settled choices. Once a choice is made, encode it only as constraints under the phase/checklist items it affects (or under **Out of scope** if the choice is a non-goal). Git history / chat is enough for "why we chose X."
- End-of-plan lists are fine for cross-cutting items that do not fit under a single checklist item:
  - **Success criteria** — whole-plan gates.
  - **Out of scope** — explicit non-goals / rejected approaches for this plan (not a pickup backlog).
  - **Deferred** — later work we still intend to do (migrates to `DEFERRED.md` when the plan is deleted).

  Prefer putting a criterion under its item when it is specific to that item.

## Preserve nested out-of-scope / deferred notes

When trimming a phase or checklist item, **do not discard** notes that lived under that item. Sort them first:

| Kind | Meaning | Where it goes |
|------|---------|----------------|
| **Later work** | We intend to do this in a future plan | Plan end **Deferred** list, or `DEFERRED.md` (see below) |
| **Non-goal / never** | Rejected approach or permanent constraint | Plan end **Out of scope**, or a standing rule / doc — **not** `DEFERRED.md` |

Then either:

1. **Promote** into the matching end-of-plan list (**Deferred** vs **Out of scope**), or
2. For **later work only**, add or merge into `DEFERRED.md` in the same commit that removes that section (see **Merge before appending** below).

Prefer (1) while the plan is still active. Use (2) when promoting would be noisy or the plan is about to be deleted anyway.

## Keep only remaining work

- After each commit that advances a plan, **edit the plan file** so it describes **only what is left**.
- **Delete** finished phases, completed checklist items, and their nested detail from the plan file. Finished work belongs in **git history**, not in the plan.
- Do **not** accumulate changelogs in the plan ("Phase 1 done… Phase 2 done…").
- Do **not** keep completed work in the plan as checked boxes. **`- [x]` is never a valid plan update** — remove the item entirely (and drop an empty phase heading).
- Trim end-of-plan **Success criteria** the same way: drop bullets that no longer apply or are already satisfied.
- Trim end-of-plan **Out of scope** only when the non-goal is obsolete or already enforced by a standing rule / doc.
- Trim end-of-plan **Deferred** (later work) only when the item is obsolete or already captured in `DEFERRED.md` / another active plan — never by silent deletion when removing a finished phase/item (see above).

### Hard gate — one commit per plan phase / checklist item

**Implementing a living plan means one git commit per completed phase (or per top-level `- [ ]` item when phases are thin).** Do **not** batch multiple finished phases into a single commit, even when implementing the whole plan in one session.

Workflow for each phase/item:

1. Implement **only that** phase/item (and its nested bullets).
2. Run the relevant tests for that slice (`run-focused-tests.md`).
3. In **that same commit**, **delete** the finished item(s) and their nested bullets from `docs/plans/…` (and drop an empty phase heading).
4. Commit, then start the next phase.

**Completing a plan checklist item (or phase) without deleting that item from the plan file in that same commit is a rule violation.**

Also:

1. **Forbidden substitutes for deletion:** `- [x]`, strike-through, "done", "completed in …", or moving finished detail into a "Shipped" / changelog section of the plan.
2. Do **not** defer the plan edit to a follow-up commit.
3. Auto-commit applies: the plan shrink is part of the intentional work for that task, not an optional docs pass.
4. **Before `git commit` on plan-advancing work**, grep the staged plan file(s) for `- [x]` / `- [X]`. If any remain, delete those items and re-stage before committing.
5. When the last in-scope item lands, that commit deletes the plan file (after moving any remaining **Deferred** pickup items to `DEFERRED.md` as required below).

The session todo list (TaskCreate/TaskUpdate) is **not** a substitute for the plan file, and checking off a todo is not shrinking the plan. Todos track this turn; the plan file tracks the work.

## Plan file lifecycle (this section is for you — do not put it in the plan)

These housekeeping rules apply to you; **do not** restate them inside plan documents (no "living plan / remaining work only", no "delete this file when done", no checklist item whose only job is deleting the plan):

- When the last remaining **in-scope** product/work item is complete:
  1. **Preserve later work only** — before deleting the plan, move still-relevant **Deferred** (pickup) bullets into the repo's deferred backlog. See **What belongs in `DEFERRED.md`** below.
  2. **Default backlog file:** `DEFERRED.md` at the repository root. Create it if missing **and** there is at least one real pickup item. Add or merge **actionable bullets only** (see below). If nothing qualifies, do **not** create or keep an empty / historical `DEFERRED.md`.
  3. If the repo already maintains an equivalent backlog under another agreed path, update that file the same way instead of inventing a second list.
  4. Then **delete** the plan file entirely.
- Do not leave empty stubs or "completed plan" archives under `docs/plans/` unless the user explicitly asks for an archive elsewhere.
- Plan content is the work itself (phases, checklists, constraints needed to implement). Meta about how plans are maintained belongs only in this rule.
- Nothing outside the plan may cite it: no phase numbers or plan paths in code, docs, or test names (`no-plan-refs-in-code.md`).

## What belongs in `DEFERRED.md`

`DEFERRED.md` is a **pickup list** of actionable later work. It is **not** a changelog, archive, provenance log, or dump of a finished plan's **Out of scope** section. The file should read as a flat (or lightly grouped) list of future tasks someone could pick up — nothing else.

### Do put in `DEFERRED.md`

- Concrete later work that was **in scope someday**, just not in the plan that just finished (or not in the phase just trimmed).
- Items phrased as future tasks ("add X", "migrate Y", "retrain when Z") that are **not** already checklist items in another **active** `docs/plans/` file.

### Merge before appending

Before adding a new bullet, read the existing list:

- If the new work **already fits** an existing bullet (same goal, substantial overlap, or a narrower case of a broader item), **reword / broaden / simplify that bullet** in place instead of adding a near-duplicate.
- Add a separate bullet only when the work is clearly distinct.
- Prefer fewer, clearer bullets over a growing pile of overlapping ones. Do not preserve old wording for "history."

### Do not put in `DEFERRED.md`

- **Permanent non-goals / rejected approaches**. Those stay in standing rules and/or the plan's **Out of scope** until the plan is deleted — then drop them if already enforced elsewhere; do not "park" them as backlog.
- **Success criteria** from a finished plan (gates for that plan, not future work).
- **History or provenance** — dated sections, "from plan X", "added when Y closed", "moved from Phase A", "archived from …", or any note about when/why the bullet entered the file. Git history is enough.
- Work that **already lives** as a `- [ ]` item in an active plan — link/point there; do not duplicate it into `DEFERRED.md`.
- Policy already stated in a global rule or standing doc.

### Litmus test

If you would not open a new plan whose next checklist item is that bullet, it does not belong in `DEFERRED.md`.
