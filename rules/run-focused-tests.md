# Run the test file, not the whole suite

_Iterate on one file; run the full suite once before committing._

While iterating on one test or one module, run **just that file**. A full-suite
run per edit wastes minutes and buries the failure you are working on.

```bash
# ❌ BAD — a full run to check one assertion you just changed
npm test

# ✅ GOOD — whatever the repo's single-file entry point is
node --test test/foo.test.js
npx vitest run test/foo.test.js
pytest tests/test_foo.py::test_bar
```

- Check the repo for an existing single-file runner or filter argument before
  inventing one — most suites have a name filter or accept a path.
- If that runner is a thin wrapper around an installed test-running package,
  the filter argument is documented in *that package's* own README, not the
  wrapper — install it and read the README (`install-before-filesystem-search.md`)
  rather than guessing at flags or reverse-engineering the wrapper's source.
- Run the **full suite once** before committing, not on every edit.
- Same rule for other slow whole-project checks (lint, typecheck, build): scope
  them to what you changed while iterating, run them whole before you commit.
- If the full run is genuinely long, start it with `run_in_background: true` and
  keep working; you are re-invoked when it exits. Do not poll it in a loop.
- Never report a test as passing that you did not run. "Should pass" is not a
  result — run it, or say you did not.
