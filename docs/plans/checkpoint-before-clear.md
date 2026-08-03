# Recognize the cheap moment to checkpoint and clear, and verify it actually happened

- [ ] Confirm what a `Stop` hook can see and do: whether it can read the current context size the
      way `session_carry()` already does, and whether it can block the turn from ending — inject
      `additionalContext` and force another turn — the way `PreToolUse` can deny a call.
- [ ] Pick the size threshold from observed firing frequency, not from the ratio alone. A threshold
      derived only by reasoning ("context is clearly bigger than the floor") is a guess
      (`rules/measure-before-recording.md`) and would be true almost immediately, nagging on nearly
      every turn. Run a candidate for a session or two and record in `usage/notes.md` how often it
      fired against how often the context had actually grown enough to matter.
- [ ] Updates to the string returned by `carried_reason` (in hooks/usage_gate.py):
      - It must say clearly that the agent should minimize tool calls while doing everything suggested, since now is when they are most expensive
      - "name any instruction the user gave that generalizes" sounds like we're just asking the agent to give the rule/skill/memory
        a title, but what it should actually do is save it in ~/.claude/projects/<PROJECT_NAME>/memory/MEMORY.md or as a plan
        in ~/github/global-claude-rules/docs/plans (regardless of what the current project is)

## Success criteria

- The idle-gap trigger fires on sessions idle past the prompt-cache TTL regardless of where the
  credit window happens to be, and never fires merely for crossing a window boundary.
- A separate, context-size-only trigger fires on a session that never wrote a plan file and never
  went idle, once its context crosses the measured threshold.
- No firing tells the user it's safe to `/clear` while something identifiably durable-but-unsaved is
  still only in the conversation — an uncommitted file, an unwritten cross-project rule, or an
  unsaved memory the agent itself would judge worth saving.
