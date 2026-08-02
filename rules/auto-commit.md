# Auto-commit after completed work

_Commit each completed task immediately, without waiting to be asked._

When you finish a completed task — implementation, fix, feature, refactor, or docs tied to that
work — **commit before your final reply**. Do not wait for the user to say "commit".

This **overrides** the system prompt's "commit only when the user asks". It does not override
branching first when you are on the default branch, and it does not authorize pushing.

## Commit only your changes

Commit only files **you** changed in this task. A dirty tree is not a violation when the remaining
dirt is not yours — leave pre-existing changes, user edits, and unrelated WIP alone, and stage
paths explicitly rather than `git add -A` when other dirt is present.

## The gate

Ending your turn with uncommitted intentional work **you made** is a rule violation. Before
replying: run `git status` in every repo you touched (`git -C DIR` for ones outside the working
directory — see `git-c-not-cd.md`), then commit your paths.

This still applies when the conversation was compacted, when tests already passed, and when the
change is only markdown. It does not apply to question-only turns, files in the scratchpad,
untracked debug dumps, secrets, or work the user said not to commit.

## One commit per item

For N requested fixes, a numbered list, or a plan with phases: complete one item, run the relevant
check for that slice (`run-focused-tests.md`), commit it, then start the next. Never batch several
finished items into one commit. For plans, the same commit deletes the finished items from the plan
file (`repo-plans.md`).

If you discover an **unrelated** bug while working on something else, commit it separately with its
own message — first if it blocks you, otherwise after. Do not land both in one diff.

## Git safety

Never update git config; never force-push or run destructive git unless asked. Check `git log -1`
for message style. Write a concise 1–2 sentence message focused on **why**, using a HEREDOC. No
empty commits.
