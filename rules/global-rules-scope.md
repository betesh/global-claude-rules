# Global rules stay project-agnostic

_These rules apply to every repo, so they must read sensibly in every repo._

The rules in this repo are loaded into **every** session regardless of which project you are working in. Write them so they make sense in any project.

## Do

- Use generic terms: **the repo**, **the plan file**, **the package**, **downstream app**, **tests**, **docs**.
- Put project-specific names, paths, fixtures, product vocabulary, and worked examples in **that repo's own** `CLAUDE.md`, `.claude/rules/`, or its plan / docs — not here.
- Keep each rule to one concern with a filename that names it. A rule you cannot summarize in one line is two rules.

## Do not

- Name a particular application, package, or fixture set in a global rule as if it were universal.
- Copy repo-local conventions into this repo when they only apply to one codebase.
- Encode facts that go stale (version numbers, someone's current branch, a URL that will move).
