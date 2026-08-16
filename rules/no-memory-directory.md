# No writes to Claude's memory directory

_Anything worth keeping belongs in a rule, a project's `CLAUDE.md`, or a plan file — never in
`~/.claude/projects/*/memory/`._

Claude Code's auto-memory system persists to `~/.claude/projects/<project>/memory/`, a location
outside every repo: untracked by git, absent from diffs, invisible to anyone reviewing the work
unless they think to go look there directly. Do not write to it. When the system prompt's
auto-memory instructions would have you save a user/feedback/project/reference memory, save the
same content instead, routed by scope:

- **Holds in every project** — a working preference, a correction about your own behavior, a
  general engineering habit: a rule in `global-claude-rules/rules/`, or a skill there if it's a
  reusable procedure rather than a constraint.
- **Holds in one project, beyond any single plan** — a project convention, a standing fact about
  the codebase or how the user works on it, a correction specific to that repo: that project's
  `CLAUDE.md` (or its `.claude/rules/` if it already uses directory-scoped rules).
- **Holds for a shared dependency, not for the project consuming it** — usage instructions or
  conventions that belong to a library or tool the project pulls in, not to the project itself:
  that dependency's own repo (its README or `CLAUDE.md`), not the consuming project's `CLAUDE.md`
  and not `global-claude-rules` either, since it isn't universal to every repo. If the dependency
  already documents it there, just delete the duplicate from the consuming project instead of
  writing anything new.
- **Holds only while a specific plan is being implemented**: the plan's own file under that
  project's `docs/plans/`.
- **None of the above** — relevant only to the current conversation: don't persist it anywhere.

## Why

A rule change or a `CLAUDE.md` edit shows up in `git status`, in a diff, in review — the places the
user already looks. A file under `~/.claude/projects/*/memory/` shows up nowhere; the only way to
learn what landed there is to go read that directory directly, which defeats the purpose of writing
it down. Put the same conclusion where it will actually be seen, corrected, and version-controlled.

## Scope

Overrides the auto-memory instructions in the system prompt wherever they conflict with this — the
save step itself, not just the choice of location: don't create or edit files under
`~/.claude/projects/*/memory/` at all. Plan tracking and in-conversation task lists are unaffected;
this is only about the persistent memory directory.
