# Global rules for Claude Code

> **Not a rule file.** Only `rules/*.md` is loaded into sessions. This README documents
> setup and is never ingested as an instruction.

Standing instructions that apply to every repository — auto-commit, living plans,
focused test runs, and so on. A `SessionStart` hook points Claude Code at
`rules/*.md` at the start of every session, so the rules bind in every project
without per-project configuration.

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

- writes a `SessionStart` hook into `~/.claude/settings.json` (or
  `$CLAUDE_CONFIG_DIR/settings.json`), preserving every other setting;
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
| `hooks/session-start.sh` | No | Emits the rule paths as session context |
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

`hooks/session-start.sh` prints a short preamble plus the absolute path of each
`rules/*.md` file. Claude Code appends that to the session context, and Claude
reads the files. The hook lists paths rather than inlining rule bodies because
hook output is size-limited.

It runs on the `startup|resume|clear|compact` matcher, so the rules are
re-established after a context compaction rather than quietly aging out.

To check the output without starting a session:

```sh
./hooks/session-start.sh
```

## Caveats

- **Subagents don't get these rules.** The hook fires for the main session only;
  agents spawned with the Agent tool start cold. Restate anything that matters in
  the subagent's prompt.
- **Project settings can't override this.** The hook is installed in user
  settings and fires everywhere. A project that needs different behavior should
  say so in its own `CLAUDE.md`.
- **Cursor no longer reads these.** The files were `.mdc` with Cursor
  frontmatter; they are now plain `.md` under `rules/`. Cursor's
  `~/.cursor/rules/` loader won't see them unless you also symlink them there.
