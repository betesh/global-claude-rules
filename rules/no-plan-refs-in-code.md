# Don't cite a plan from the code

_Comments, docs, names, and tests must not reference a plan, a phase, or a checklist item — those are deleted when the work lands._

A plan describes work that is not finished. It shrinks with every commit and is deleted when the last item lands, so anything pointing at it — "what Phase 2 adds", "the gate from step 3", "see `docs/plans/foo.md`" — is a dangling pointer by the time a reader arrives, and they cannot recover what it meant.

## Instead, state the thing itself

```js
// ❌ BAD — the plan is gone by the time anyone reads this
// Retried here for Phase 2.

// ✅ GOOD — states the condition being handled
// Retried once: the server answers 503 while it warms a cold pool, and succeeds on the
// second call.
```

If a comment needs the plan to make sense, its reason has not been written down yet. Write the reason.

## Scope

Applies to source comments and docstrings, README and other docs, test / suite names, fixture names, error and log messages, and identifiers (`phase2Threshold`). Also to plan-relative wording that outlives the plan: "the new behaviour", "the old path", "for now", "until the rewrite". Also to narrating a prior implementation in a comment ("this used to be X", "previously computed as Y") — state what the code does now; a before/after comparison belongs in the commit message, where the diff gives it meaning.

A plan reference belongs in exactly three places, all of which are dated records rather than current instructions: **inside the plan file** (phases may cite each other freely), **commit messages and PR descriptions**, and a **tracker/issue link** that outlives the plan — when code genuinely needs to point at future work, point at the repo's deferred backlog or an issue, not at a phase.
