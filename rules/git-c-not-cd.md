# Use `git -C DIR`, not `cd DIR && git`

_Target a repo other than the current project with a path flag; never change the shell's working directory._

When running a git command against a repository other than the one the current project's working directory already sits in, pass the path with `-C` instead of changing directories. When the command targets the current project itself, run plain `git ...` with no `-C` — the working directory already points at that repo, so `-C` only adds noise.

```bash
# ❌ BAD — mutates shell state, and the `cd` can trigger a permission prompt
cd ../other-repo && git log --oneline -5

# ✅ GOOD — targeting a different repo
git -C ../other-repo log --oneline -5

# ✅ GOOD — targeting the current project: no -C needed
git log --oneline -5
```

## Why

- The Bash tool's working directory **persists between calls**, so a stray `cd` silently changes where later commands run — including commands in a later turn, after you have forgotten the `cd`.
- `cd` into an unrelated directory often needs its own approval, while `-C` does not.
- Each command stays self-describing: the repo it targets is visible in the command itself.
- Adding `-C .` (or the current project's own path) to every git command in the current project is pure noise — the working directory already is that repo, so the flag conveys nothing and just adds a fixed cost repeated on every call.

## Scope

- Applies to **every** git subcommand (`status`, `diff`, `log`, `show`, `add`, `commit`, …) and to chained/piped invocations, whenever the target is a repo other than the current project.
- Applies to inspecting sibling repos, dependency checkouts, and the rules repo — when the current working directory is not already inside them.
- Does not apply to git commands run against the current project itself: use plain `git ...`, no `-C`.
- Other tools with an equivalent flag (`npm --prefix DIR`, `make -C DIR`, `pytest --rootdir`, `cargo --manifest-path`) should follow the same split: the flag for another project, nothing for the current one.
- For file reads, edits, and searches, pass an absolute path to Read/Edit/Write/Grep/Glob rather than `cd`-ing first. The file tools do not depend on the shell's working directory at all.
