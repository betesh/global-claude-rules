# Global rules stay project-agnostic

_These rules apply to every repo, so they must read sensibly in every repo._

The rules in this repo are loaded into **every** session regardless of which project you are working in. Write them so they make sense in any project.

## Do

- Use generic terms: **the repo**, **the plan file**, **the package**, **downstream app**, **tests**, **docs**.
- Put project-specific names, paths, fixtures, product vocabulary, and examples lifted from a real codebase in **that repo's own** `CLAUDE.md`, `.claude/rules/`, or its plan / docs — not here.
- Illustrate with vocabulary every programmer already has: files, requests, retries, caches, timeouts, tests. Examples are welcome; examples that need a domain briefing are not.
- Keep each rule to one concern with a filename that names it. A rule you cannot summarize in one line is two rules.

## Do not

- Name a particular application, package, or fixture set in a global rule as if it were universal.
- Copy repo-local conventions into this repo when they only apply to one codebase.
- Encode facts that go stale (version numbers, someone's current branch, a URL that will move).
- **Explain a rule in one project's domain vocabulary.** A leak needs no proper noun: an example whose nouns, units, or thresholds only mean something once you know a particular problem domain is as repo-specific as one that names the product, and it reads as noise everywhere else.

## Check before you commit

Read your example as someone working in an unrelated codebase — a payments API, a game engine, a CLI. Can they tell what it demonstrates without asking what any of its terms mean? If not, rewrite it; renaming the identifiers is not enough when the whole scenario is domain-bound.

The usual source of a leak is the code you were working in when the rule occurred to you. That is the example most in need of replacing, and the least likely to look wrong while you are still holding its context.
