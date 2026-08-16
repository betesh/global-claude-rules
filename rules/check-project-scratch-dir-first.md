# Check the project's own scratch convention before the session scratchpad

_A project's `CLAUDE.md` may already document its own tmp/scratch directory — check it before
defaulting to `/tmp` or the session scratchpad._

Before writing a temporary file — a debug script, an intermediate render, a throwaway data dump —
check whether the current project's `CLAUDE.md` documents its own scratch directory (e.g. a
gitignored `./tmp`). If it does, use that: it's already the convention other tooling and prior
sessions in that repo expect. Fall back to the session scratchpad only when the project has no
documented convention of its own.

## Scope

Applies before creating any throwaway file in a project that has its own `CLAUDE.md`.
