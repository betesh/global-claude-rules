# Verify before assuming exclusive access to a shared checkout

_More than one Claude Code session can point at the same working tree at once — verify state and
identity before acting like you're alone in it._

A repo checkout can be driven by more than one session concurrently. There is one working tree, so
uncommitted and staged changes are shared: one session's `git add`/`git commit` can pick up another
session's in-progress edits, and a file already matching `HEAD` may mean another session already
committed it, not that no work is needed.

- Before committing, run `git status` / `git diff --cached` rather than assuming the index holds
  only this session's changes. Don't assume authorship of a commit whose message you didn't write.
- When told another session or process is actively working on the same checkout, stop making
  further edits immediately — including read-only audits, since a broad sweep can touch files the
  other session is mid-editing and compare them against a state that's already stale. Finish only
  what's already committed or is trivially safe, then wait for the user to say it's clear. On
  resume, re-run any broad sweep from scratch rather than trusting earlier findings.
- Don't conclude a PID or session is "another agent" from circumstantial evidence — a matching
  working directory, matching prompt text, nearby timestamps in a log. Verify by walking the
  current shell's own process ancestry (`$$` → parent PID → repeat) up to the enclosing `claude`
  process, and compare that PID against the one in question.
- `ps`'s command column shows a `claude` process's *original* invocation argv, frozen at process
  start — `/clear` resets the conversation but not that argv, so a session that was launched with
  one task and later `/clear`ed into a different one still shows the old task text next to a live,
  *current* PID. A `ps` hit whose command line names a task that looks stale, or unrelated to what
  you're doing now, is not evidence of a second agent — it is at least as likely to be this same
  session before its own `/clear`. Don't reason about it from the argv text at all; run the
  ancestry walk and compare PIDs, which resolves it either way.

- When creating a new git worktree (via `EnterWorktree` or a manual `git worktree add`) as an
  isolation mechanism for concurrent work, add its specific path to the project's `permissions.ask`.
  A freshly created worktree is a context switch worth surfacing explicitly — it's easy to lose
  track mid-session of which checkout is active.

## Scope

Applies to any repo that may be worked by more than one session at once. A project's own
convention for keeping concurrent sessions isolated (e.g. giving each its own git worktree) belongs
in that project's `CLAUDE.md`, not here — this rule covers verifying state and identity when
isolation isn't otherwise guaranteed, and the permission default for a newly created worktree.
