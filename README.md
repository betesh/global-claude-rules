# Global rules for Claude Code

> **Not a rule file.** Only `rules/*.md` is loaded into sessions. This README documents
> setup and is never ingested as an instruction.

Standing instructions that apply to every repository — auto-commit, living plans,
focused test runs, and so on. Two hooks point Claude Code at `rules/*.md`:
`SessionStart` for the main session and `SubagentStart` for every subagent. The
rules bind in every project, and in every agent, without per-project
configuration.

## Install

Clone anywhere, then run the installer:

```sh
git clone <this-repo> ~/some/path/global-rules
~/some/path/global-rules/install.sh
```

Start a new session (or `/clear`) and the rules load. Nothing else references
the clone's location — the hook resolves its own path, and the installer records
that absolute path in your settings.

The installer:

- writes a `SessionStart` and a `SubagentStart` hook into
  `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR/settings.json`), preserving
  every other setting;
- backs the file up to `settings.json.bak` first;
- replaces any hook a previous clone of this repo installed, so re-running it is
  safe and idempotent.

```sh
./install.sh              # install or update
./install.sh --uninstall  # remove the hook, leave other settings alone
./install.sh --help
```

**If you move the clone, re-run `./install.sh`** — the recorded path is absolute.

Requires `python3` (used only to edit the JSON settings file safely).

## Layout

| Path | Loaded into sessions? | What it is |
|------|----------------------|------------|
| `rules/*.md` | **Yes** — every file, every session | The rules themselves |
| `hooks/load-rules.sh` | No | Emits the rule paths as session context |
| `install.sh` | No | Registers the hook in your Claude Code settings |
| `README.md` | No | This file |

Rules live in `rules/` specifically so that adding docs at the repo root can
never be mistaken for a rule.

## The rules

| File | Rule |
|------|------|
| `auto-commit.md` | Commit each completed task immediately, without being asked; only your own changes |
| `repo-plans.md` | Plans live in the owning repo's `docs/plans/`, shrink every commit, and are deleted when done |
| `run-focused-tests.md` | Iterate on one test file; run the full suite once before committing |
| `stash-dont-discard.md` | Stash experimental work you might return to; never `git checkout --` it |
| `git-c-not-cd.md` | Target other repos with `git -C DIR`, never `cd DIR && git` |
| `collapse-passthroughs.md` | Delete no-op wrappers and rename-only aliases in the change set that creates them |
| `global-rules-scope.md` | Keep these rules project-agnostic; repo-specific conventions go in that repo |
| `rules-repo-workflow.md` | This repo is a repo — rule edits get committed like any other work |

## Adding a rule

Drop a `.md` file in `rules/`. It is picked up on the next session start; no
reinstall needed. One concern per file, project-agnostic, and short — every rule
is read in full at the start of every session, so length is a real cost.

## How it works

`hooks/load-rules.sh` prints a short preamble plus the absolute path of each
`rules/*.md` file. Claude reads the files from there. The hook lists paths rather
than inlining rule bodies because hook context is size-limited.

It is registered on two events:

| Event | Matcher | Matches on | Output |
|-------|---------|-----------|--------|
| `SessionStart` | `startup\|resume\|clear\|compact` | session `source` | plain stdout |
| `SubagentStart` | `*` | `agent_type` | JSON `hookSpecificOutput.additionalContext` |

`SessionStart` includes `compact` so the rules are re-established after a context
compaction rather than quietly aging out. `SubagentStart` fires once per spawned
agent and only accepts context as JSON, which is why the installer registers it
as `load-rules.sh --json`.

To check both outputs without starting a session:

```sh
./hooks/load-rules.sh          # what the main session sees
./hooks/load-rules.sh --json   # what a subagent sees
```

To load the rules for only some agent types, change the `SubagentStart` matcher
from `*` to an alternation of agent names, e.g. `general-purpose|Plan`. Read-only
agents like `Explore` arguably don't need them, at the cost of one more thing to
keep in sync.

## Caveats

- **Subagents read the rules themselves.** Each spawned agent spends a few Read
  calls on them before starting. That is the price of the rules actually binding;
  narrow the matcher if it becomes a problem.
- **Project settings can't override this.** The hooks are installed in user
  settings and fire everywhere. A project that needs different behavior should
  say so in its own `CLAUDE.md`.
- **Cursor no longer reads these.** The files were `.mdc` with Cursor
  frontmatter; they are now plain `.md` under `rules/`. Cursor's
  `~/.cursor/rules/` loader won't see them unless you also symlink them there.
