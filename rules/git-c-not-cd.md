# Use `git -C DIR`, not `cd DIR && git`

_Target another repo with a path flag; never change the shell's working directory._

When running a git command against a repository other than the current working directory, pass the path with `-C` instead of changing directories.

```bash
# ❌ BAD — mutates shell state, and the `cd` can trigger a permission prompt
cd ../other-repo && git log --oneline -5

# ✅ GOOD
git -C ../other-repo log --oneline -5
```

## Why

- The Bash tool's working directory **persists between calls**, so a stray `cd` silently changes where later commands run — including commands in a later turn, after you have forgotten the `cd`.
- `cd` into an unrelated directory often needs its own approval, while `-C` does not.
- Each command stays self-describing: the repo it targets is visible in the command itself.

## Scope

- Applies to **every** git subcommand (`status`, `diff`, `log`, `show`, `add`, `commit`, …) and to chained/piped invocations.
- Applies to inspecting sibling repos, dependency checkouts, and the rules repo alike.
- Other tools with an equivalent flag (`npm --prefix DIR`, `make -C DIR`, `pytest --rootdir`, `cargo --manifest-path`) should use it for the same reasons.
- For file reads, edits, and searches, pass an absolute path to Read/Edit/Write/Grep/Glob rather than `cd`-ing first. The file tools do not depend on the shell's working directory at all.
