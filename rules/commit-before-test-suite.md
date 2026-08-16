# Commit before running the test suite, not after

_When a repo has CI that mirrors the local suite, commit finished work first and let CI start
running it while you run it locally too — don't wait for a local pass before committing._

CI often has more headroom than the machine you're developing on, so it can finish the same suite
faster. Committing first lets CI start immediately; running the suite locally afterward runs it a
second time in parallel rather than gating the commit on it. If the local run turns up a problem,
amend the commit.

This governs commit **order** relative to the test run only — it doesn't change whether a commit
happens or which tests to run locally first: `auto-commit.md` still governs that completed work
gets committed, and `run-focused-tests.md` still governs running the focused file before the full
suite.

## Scope

Applies once a repo has CI configured to run the same suite (or a superset of it) on push. Without
that, there's no second, faster run to overlap with — run tests before committing as usual.
