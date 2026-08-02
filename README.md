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
| `hooks/usage-window.sh` + `usage_window.py` | No | Emits the credit-window state as session context |
| `hooks/plan-written.py` | Only when it fires | Nudges toward `/clear` after a plan file is written whole |
| `hooks/write-settings-hook.py` | No | Edits settings.json for both installers |
| `install.sh` | No | Registers the rules hooks in your Claude Code settings |
| `install-usage-hook.sh` | No | Registers the usage-window hook |
| `usage/notes.md` | No | Committed conclusions about the credit window |
| `usage/events.jsonl` | No | Raw usage observations, appended by agents — gitignored |
| `README.md` | No | This file |

Rules live in `rules/` specifically so that adding docs at the repo root can
never be mistaken for a rule.

## The rules

| File | Rule |
|------|------|
| `auto-commit.md` | Commit each completed task immediately, without being asked; only your own changes |
| `run-focused-tests.md` | Iterate on one test file; run the full suite once before committing |
| `git-c-not-cd.md` | Target other repos with `git -C DIR`, never `cd DIR && git` |
| `usage-limits-and-context.md` | Pool what agents learn about the shared credit window in `usage/`; treat context size as spend |

## The plan-written hook

`install.sh` also registers a `PostToolUse` hook on `Write`. When the file written
is under `docs/plans/`, it adds one paragraph of context: make the record durable,
commit, then tell the user this is a good moment to `/clear`.

That moment is when a session's context is worth least and costs most — what
matters was just written to a file, and the conversation that produced it would
otherwise be re-sent on every request of the implementation that follows.

It is a hook rather than a rule because a rule is re-read on every request of
every session (~0.4 points of a window per 1,000 tokens) while this costs nothing
until it applies. `Edit` is deliberately not matched: trimming finished items
from a plan is routine, replacing the file is not.

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

## The usage-window hook

`usage-limits-and-context.md` asks agents to predict when shared credit runs
out. `install-usage-hook.sh` installs a second `SessionStart` hook that answers
that question **before the model runs**, which is the only moment the answer is
free:

```sh
./install-usage-hook.sh              # install / update
./install-usage-hook.sh --uninstall  # remove, leaving the rules hooks alone
```

It reads two local sources and prints a few lines of context:

- `usage/events.jsonl` in this repo — the window start and any percentage the
  user reported. It maintains the start itself: whenever the window it works out
  is not the one the log's newest boundary line names, it appends a `renewed`
  carrying that start in `startedT`, so the record stays current with no agent
  spending a turn on it and no line ever needing to be pruned.
- the session transcripts under `$CLAUDE_CONFIG_DIR/projects` (else
  `~/.claude/projects`) — every assistant message carries a `message.usage`
  object, so summing the ones inside the window measures what **all** agents on
  this machine have actually sent. One request writes many streaming lines
  sharing a `requestId`, each with running totals, so the last line per
  `requestId` is that request's cost.

Tokens are not percent. The hook prints tokens always, and a percentage estimate
only once a `usage-report` event exists to calibrate against — two of them give a
better ratio than one. When credit is already out, it says so loudly instead.

The window length it assumes is **5 hours**, unconfirmed by measurement here;
override with `CLAUDE_USAGE_WINDOW_MINUTES`, and a `usage-report` that disagrees
makes it say so. It matches `startup|clear` only — `resume` and `compact`
continue a session that already saw this. Any error exits silently: a session
never fails to start because of it.

Measured on this machine at install time: **0.22 s** over 85 MB of transcripts,
after old lines are rejected on the raw text rather than parsed.

## Caveats

- **Subagents read the rules themselves.** Each spawned agent spends a few Read
  calls on them before starting. That is the price of the rules actually binding;
  narrow the matcher if it becomes a problem.
- **Project settings can't override this.** The hooks are installed in user
  settings and fire everywhere. A project that needs different behavior should
  say so in its own `CLAUDE.md`.

## Skills

Situational rules load on demand instead of sitting in every session's
context. `install.sh` symlinks them into the Claude skills directory.

| skill | what it covers |
|---|---|
| `repo-plans` | Plans live in the owning repo's `docs/plans/`, shrink every commit, and are deleted when done |
| `stash-dont-discard` | Stash experimental work you might return to; never `git checkout --` it |
| `collapse-passthroughs` | Delete no-op wrappers and rename-only aliases in the change set that creates them |
