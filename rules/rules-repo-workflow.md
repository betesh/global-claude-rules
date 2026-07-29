# The rules repo is a repo

_Edits to these rules follow the same workflows as any other repository, including auto-commit._

The directory that holds these global rules is itself a **tracked git repository**. Its absolute path is given in the SessionStart context that loaded these rules; it is **not** a fixed location, so never hard-code a path to it — read the one you were given.

## When you edit that repository

If you create, modify, or delete files **inside the rules repository** (even when the session's working directory is a different project):

- Apply the same repo workflows as for any other git repo you touch — including **auto-commit** after completed intentional work (`auto-commit.md`).
- Run `git -C <rules-repo> status` / `add` / `commit` **in the rules repository**, not only in the workspace project (`git-c-not-cd.md`).
- Ending a turn with intentional uncommitted changes in the rules repository is a rule violation (same hard gate as auto-commit).

Do not skip committing rule edits because they sit outside the current working directory.

## Adding or changing a rule

- One concern per file, in `rules/`, as `.md`. The filename is the rule's identifier; other rules cite it by filename.
- Everything in `rules/*.md` is loaded verbatim into every session. Cost is real — say it once, in the shortest form that still binds.
- Nothing outside `rules/` is loaded. `README.md`, `install.sh`, and `hooks/` are project files, not rules; do not write behavioral instructions into them expecting to be bound by them.
- A rule that only ever applies to one project belongs in that project instead (`global-rules-scope.md`).
