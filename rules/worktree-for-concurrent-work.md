# Check for concurrent work before starting, and worktree only when it's safe

_Before starting work in a repo, check whether another agent is active there. If the work is
unlikely to conflict, move to a worktree kept in sync with the main checkout; if it's likely to
conflict, say so instead of trusting the worktree to prevent it._

A worktree isolates the *working tree* during editing. It does nothing about the eventual merge —
two branches touching the same lines still conflict when one lands on the other, worktree or not.
Reach for a worktree to avoid stepping on another agent's uncommitted edits, not to avoid a merge
conflict that was always coming.

## 1. Check whether another agent is active

- `ps` (or equivalent) for another process rooted in this repo's directory.
- Whether files are currently being edited: `git status` for uncommitted changes that aren't
  yours, recent mtimes on files you haven't touched.

Do this check even when the task looks solo and the run is short — a live near-miss: two sessions
shared one checkout (no worktree) on unrelated files; while one session had changes `git add`-ed,
the other ran a commit that swept up those staged files into its own unrelated commit before
self-correcting. No data was lost, but it was close, and would have been prevented entirely by a
`ps` check before the first edit. "Unlikely to conflict on files" (step 2) does not mean "safe to
share a working tree" — a shared index/staging area is a hazard on its own, independent of whether
the *file contents* would ever conflict.

See `concurrent-sessions.md` for confirming a PID is actually another agent rather than guessing
from circumstantial evidence, and for what to do once you know work is shared.

## 2. If another agent is active, judge conflict potential

Compare the files/areas its in-progress changes touch against what this task needs to touch.

- **Likely to conflict** (same files, or areas tightly coupled to them): tell the user directly —
  moving to a worktree will not prevent the conflict, only delay where it's discovered, since the
  conflict is resolved at merge time regardless of which working tree either agent used. Let the
  user decide whether to proceed anyway.
- **Unlikely to conflict** (disjoint files/areas): continue to step 3.

## 3. Use an existing worktree, or create one

- Run `git worktree list`. If one is idle — no other agent using it, per the check in step 1 —
  update it to the main worktree's current commit and do the work there.
- If no idle worktree exists, create one under `/tmp`.

Scope every git and test operation to the worktree you're using (`git -C <worktree>`, per
`git-c-not-cd.md`) — never assume the main checkout mirrors it, and never run a destructive git
command against either without checking `git status` first.

When creating a new worktree, add its specific path to the project's `permissions.ask`, per
`concurrent-sessions.md` — a freshly created worktree is a context switch worth surfacing
explicitly.

## Scope

Applies to any repo that may be worked on by more than one agent concurrently. Doesn't mandate a
worktree for solo work with no evidence of concurrent activity — the checks in step 1 are cheap,
not a reason to worktree every task.
