# Auto-commit after completed work

_Commit each completed task immediately, without waiting to be asked._

When you finish a **completed task** (implementation, fix, feature, refactor, or docs tied to that work), **create a git commit immediately** if there are changes to commit. Do **not** wait for the user to say "commit".

**This rule overrides** the Claude Code system prompt's "Commit or push only when the user asks." If those conflict, **this file wins**. It does **not** override the instruction to branch first when you are on the default branch, and it does **not** authorize pushing — commit locally; push only when asked.

## Ownership — commit only your changes

**Commit only files you changed in this conversation/task** (edits, adds, or deletes you performed with tools).

- "Intentional work" means **your** intentional work for the completed task — **not** everything `git status` shows.
- **Do not** commit pre-existing dirty files, user edits, or unrelated WIP that was already dirty when the turn started, or that you did not touch.
- A dirty tree is **not** a rule violation when the remaining dirt is not yours. There is **no** clean-tree requirement for unrelated dirt.
- When staging, stage **only** the paths you changed for the task (avoid `git add -A` / `git add .` when unrelated dirt is present).

## Hard gate (rule violation if skipped)

**Ending your turn with uncommitted intentional work you made is a rule violation.**

After any implementation, fix, refactor, or docs update that touched tracked files:

1. Run `git status` (and `git diff` if the change set is unclear).
2. If `git status` shows **modified, added, or deleted tracked files that you changed this task** (not excluded below), you **MUST** `git add` those paths and `git commit` **before** your final user-visible reply.
3. Your last tool calls before replying should include a successful commit of **your** changes (or a clear reason commit was impossible), not only code edits and tests.

Do **not** assume the user will ask you to commit later. Do **not** end with a summary of "what remains" that includes "uncommitted changes" you were responsible for committing.

This gate still applies when:

- The conversation was **compacted** or context was truncated — re-run `git status` and commit anything still dirty **from your work**.
- You already ran tests — passing tests does not replace committing.
- The change includes only `ROADMAP.md`, `docs/`, or other markdown — commit with the code unless the user listed them as separate fixes.
- The files live **outside the current working directory** (another repo, or the rules repo itself) — use `git -C DIR` and commit there too. See `rules-repo-workflow.md` and `git-c-not-cd.md`.

## Multi-fix requests

If the user asks for **N fixes** (especially **"1 commit per fix"** or a numbered list):

1. Complete **one** fix.
2. Run the relevant check for that slice when the change warrants it (see `run-focused-tests.md`).
3. **Commit that fix before starting the next one.**
4. Repeat until all items are done.

Never batch several completed fixes into one commit, and **never end your turn with uncommitted fixes** the user already asked for.

## Living plans (`docs/plans/`)

Implementing a plan with multiple phases or top-level checklist items is a multi-item request:

1. **One commit per completed phase** (or per top-level `- [ ]` item).
2. Shrink the plan in that same commit (delete finished items — see `repo-plans.md`).
3. Do **not** implement all phases and land them as a single mega-commit.

This applies even when the user says "implement the plan" without repeating "1 commit per phase."

## Discovered unrelated bugs during a task

When working on task **A**, if you discover an unrelated bug **B**, do **not** land both in one commit.

Required workflow:

1. Stop mixing **B** into **A**'s diff.
2. Fix **B** with the smallest correct change (and tests when appropriate).
3. Commit **B** on its own with a message describing the bug and fix.
4. Resume task **A** and commit **A** separately when complete.

Treat **B** as separate when it is a pre-existing defect, regression, or masking correctness issue unrelated to **A**'s goal. If **B** blocks **A**, still commit **B** first, then continue **A** in a follow-up commit.

## Mandatory before ending your turn

Use this checklist literally:

- [ ] `git status` run — in **every** repo you touched, via `git -C DIR` for ones outside the working directory
- [ ] If this commit advances a living plan under `docs/plans/`, finished checklist items were **deleted** from the plan (no `- [x]` left) in the same commit
- [ ] Intentional tracked changes **you made** committed (or user explicitly said not to commit)
- [ ] No secrets in the commit
- [ ] Final reply does not leave the user to discover uncommitted work **from this task**
- [ ] Pre-existing / user dirty files you did not change were left uncommitted

If you fixed a bug and also updated `ROADMAP.md`, `README.md`, or `docs/` as part of the **same** fix, commit together. If they are **separate** fixes the user listed separately, use **separate commits**.

## When to commit

- Completed implementation/fix/update with file changes → commit before ending your turn.
- Documentation and backlog updates the user asked for or that record completed work → commit in the same turn.
- Multiple independent items in one request → **one commit per completed item**.
- Living-plan work → **one commit per completed phase / top-level checklist item** (see above and `repo-plans.md`).
- Question-only or review-only (no edits) → do not commit.
- User said **not** to commit, or asked for a PR without committing → follow that instead.

## When not to commit

- No file changes, or only transient artifacts (e.g. `coverage/`).
- Secrets or credentials (`.env`, auth tokens).
- Files written to the session **scratchpad directory** — those are outside the repo by design and are never committed.
- Untracked debug dumps the user did not ask to keep (e.g. one-off `.json` logs, scratch images) — leave untracked unless asked to add them.
- Pre-existing dirty files, user edits, or unrelated WIP you did not change this task — leave them alone unless the user explicitly asks you to commit them.

## Git safety

- Never update git config; never force-push or other destructive git unless explicitly requested.
- Before committing: `git status`, `git diff`, `git log -1` for message style.
- Write a concise 1–2 sentence message focused on **why**.
- Use a HEREDOC for the commit message.
- Do not create empty commits.
