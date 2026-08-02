---
name: stash-dont-discard
description: Stash experimental work with a findable message instead of reverting it. Load this before removing uncommitted work from the tree for any reason — a failing experiment, work that must land in a different order, or a tree that has to be clean before continuing. Triggers on "revert", "discard", "git checkout --", "undo my changes", "clean the tree", "back out that change", "start over".
---

# Stash, do not discard

_Experimental work you might return to gets stashed with a findable message, never reverted._

When an experiment has to come out of the tree — it fails a check, it needs to land in a different
order, or the tree must be clean before you can continue — **stash it, do not `git checkout --`
it.**

```bash
# ❌ BAD — the work is gone; rewriting it from a description costs the same time twice
git checkout -- src/

# ✅ GOOD
git stash push -m "<what it does>: <what blocked it>" src/
```

- Write a message that says what the work does **and** what blocked it. That is what makes the
  entry findable and re-runnable later.
- `git stash list` and `git stash show -p stash@{n}` before assuming an entry is stale. Restore
  with `git stash pop`, or `apply` to keep the entry.
- This matters most for work you have already **measured**. Measurements are the expensive part;
  discarding the code that produced them means paying for them again.
- The cost is not only wall-clock. Rewriting discarded work spends context and session usage on
  output you already produced once, and that budget is what limits how far the task gets. A stash
  entry costs nothing to keep.
- Reverting is still right for a change that is simply **wrong** — a mistaken edit, a debugging
  probe, a dead end you will not revisit. Stash what you expect to come back to.
- Say in your summary that the work is stashed and under what message, so it is not silently lost.
