# Global rules for Claude Code

> **Not a rule file.** Only `rules/*.md` is loaded into sessions. This README documents
> setup and is never ingested as an instruction.

Standing instructions that apply to every repository — auto-commit, living plans,
focused test runs, and so on. Claude Code loads `~/.claude/rules/*.md` as global
instructions in every session, in every project, without per-project
configuration — so this repo's rules bind wherever a symlink at that path points
into `rules/`.

## Install

Clone anywhere, then symlink the rules and skills into place — see
[Symlinks](#symlinks) below. There is no installer for either: both are a single
`ln -s`, and scripting a one-line command just adds a file to keep in sync.

One thing still needs a script, because it edits `settings.json` rather than
just placing a symlink:

```sh
./install-hooks.sh            # registers all five hooks below
./install-hooks.sh --uninstall
```

It backs up `settings.json` to `settings.json.bak` first, and is safe to re-run
after moving the clone (the recorded hook paths are absolute). Requires
`python3`, used only to edit the JSON settings file safely.

## Symlinks

```sh
ln -s /path/to/this/clone/rules ~/.claude/rules

mkdir -p ~/.claude/skills
for d in /path/to/this/clone/skills/*/; do
    ln -s "$d" ~/.claude/skills/"$(basename "$d")"
done
```

Symlinked rather than copied, so editing the checkout takes effect without
redoing either step. Whether a subagent (spawned via the Agent tool) also picks
up `~/.claude/rules` the same way a main session does hasn't been confirmed here
— check before relying on a rule binding inside one.

## Layout

| Path | Loaded into sessions? | What it is |
|------|----------------------|------------|
| `rules/*.md` | **Yes** — every file, every session, via the `~/.claude/rules` symlink | The rules themselves |
| `skills/*` | Only when invoked | Situational instructions, via the `~/.claude/skills` symlinks |
| `hooks/usage-window.sh` + `usage_report.py` | No | SessionStart: emits the credit-window state as session context |
| `hooks/usage-gate.sh` + `usage_gate.py` | No | UserPromptSubmit: drops a prompt once the window is spent |
| `hooks/usage-tool-gate.sh` + `usage_tool_gate.py` | Only when it fires | PreToolUse: denies an individual tool call once the window's estimate is close enough to the gate that this call could be the one that crosses it |
| `hooks/edit-payload-warn.sh` + `edit_payload_warn.py` | Only when it fires | PreToolUse (matcher `Edit`): warns, without blocking, once one file's cumulative `Edit` payload this session exceeds the file's own size |
| `hooks/usage_common.py` | No | Log/transcript logic shared by the report and gate scripts above |
| `hooks/checkpoint-stop.sh` + `checkpoint_stop.py` | Only when it fires | Stop: nudges a checkpoint once context is large and the session never went idle |
| `hooks/write-settings-hook.py` | No | Edits settings.json; called once by `install-hooks.sh` with all five hook entries |
| `install-hooks.sh` | No | Registers (or removes) all five hooks above |
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

## The checkpoint-stop hook

`install-hooks.sh` also registers a `Stop` hook. `usage-gate.sh`'s own
carried-context nudge only fires once a session goes idle past the
prompt-cache TTL — a session that stays continuously active never crosses that
gate no matter how large its context gets. This hook is the complementary
trigger: at the end of every turn, it checks context size alone, and once a
session crosses `CLAUDE_CHECKPOINT_CONTEXT_TOKENS` (default: the same guess as
`CARRY_AT` in `usage_common.py`) it blocks the turn from ending with a nudge to
check `git status`, save anything durable, and tell the user this is a good
moment to `/clear` or `/compact`.

It fires at most once per session — it logs a `checkpoint-nudged` event and
checks for one before firing again, since blocking a `Stop` forces another turn
whose own request only adds to the context that triggered it, and nothing else
would stop it asking again.

## The tool gate

`usage-gate.sh` only checks the estimate once per prompt, at the moment it is
submitted. A prompt that starts safely below `GATE_AT_PCT` can go on to
dispatch many tool calls — each one its own request that resends the whole
conversation — so the estimate can cross the gate mid-flight, and the next
check only comes after it already has.

`install-hooks.sh` also registers a `PreToolUse` hook (`usage-tool-gate.sh`)
that closes that gap: it fires before every individual tool call and denies it
once too few requests' worth of budget remain, computed as
`(GATE_AT_PCT - estimate) × per_pct` divided by the last request's context size
(read straight from the transcript, the same figure `usage-window.sh` already
reports). It fires once per tool call, but several calls issued in parallel
share one request's cost, so it recomputes calls-remaining fresh on every
firing rather than counting firings down — siblings in one batch always reach
the same decision.

Its deny reason points at sleeping until the window renews, per
`usage-limits-and-context.md` — the hook itself has no way to make a session
wait, only to refuse. `CLAUDE_TOOL_GATE_MARGIN_CALLS` (default 5) sets how many
calls of headroom it insists on; the default is an unmeasured guess pending a
live observation of how far its denial lands from where `usage-gate.sh` would
have refused anyway.

## The edit-payload warning

Every `Edit`'s `old_string`/`new_string` stays in context for every request
that follows it, so a file edited piecemeal enough times can end up costing
more than a single `Write` of the whole file would have (measured cases in
`usage/notes.md` at 1.3–2.5x a file's own size after a few dozen edits).

`install-hooks.sh` registers a `PreToolUse` hook (`edit-payload-warn.sh`)
matching only `Edit`. It recomputes, from this session's own transcript, the
running total of `old_string`+`new_string` lengths against one file, and once
that total (including the call about to run) exceeds the file's current size
on disk, it adds a note suggesting a `Write` instead — without blocking the
edit. Stateless like the tool gate above: no counter to drift, just the
transcript read fresh each time.

## Adding a rule

Drop a `.md` file in `rules/`. It is picked up on the next session start; no
reinstall needed. One concern per file, project-agnostic, and short — every rule
is read in full at the start of every session, so length is a real cost.

## The usage-window hook

`usage-limits-and-context.md` asks agents to predict when shared credit runs
out. `install-hooks.sh` also registers a `SessionStart` hook that answers that
question **before the model runs**, which is the only moment the answer is free.

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

Paired with it is the `UserPromptSubmit` gate (`usage-gate.sh`), which drops a
prompt outright rather than spend a request against a window already spent.

## Caveats

- **Whether subagents inherit `~/.claude/rules` the same way a main session
  does is unconfirmed here** — see [Symlinks](#symlinks).
- **Project settings can't override these hooks.** All four are installed in
  user settings and fire everywhere. A project that needs different behavior
  should say so in its own `CLAUDE.md`.

## Skills

Situational rules load on demand instead of sitting in every session's
context — see [Symlinks](#symlinks) for how they get into the Claude skills
directory.

| skill | what it covers |
|---|---|
| `repo-plans` | Plans live in the owning repo's `docs/plans/`, shrink every commit, and are deleted when done |
| `stash-dont-discard` | Stash experimental work you might return to; never `git checkout --` it |
| `collapse-passthroughs` | Delete no-op wrappers and rename-only aliases in the change set that creates them |
