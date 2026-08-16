# Use `./tmp/claude-scratchpad` for scratch files

_Every project's throwaway files go in `./tmp/claude-scratchpad` — gitignored, and never mentioned
in that project's own `CLAUDE.md`._

Before writing a temporary file — a debug script, an intermediate render, a throwaway data dump —
write it to `./tmp/claude-scratchpad` in the current project. This is a fixed convention, so an
individual project's `CLAUDE.md` does not need to say so.

The first time you use `./tmp/claude-scratchpad` in a given project, make sure it's covered by that
project's `.gitignore`, adding an entry if it's missing.

If `./tmp` already holds scratch files from before this convention, move them into
`./tmp/claude-scratchpad` before using them.
