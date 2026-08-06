# Install a dependency before searching the filesystem for its source

_To read a dependency's API, install it through the project's package manager first — not `find`
across the whole machine._

```bash
# ❌ BAD — scans the whole machine for a copy that may not even be the right version
find / -iname "*some-package*" 2>/dev/null

# ✅ GOOD — installs it into the project, then reads the real, in-use copy
npm install
cat node_modules/some-package/README.md
```

## Why

The package manager already knows how to fetch the dependency into a location scoped to the repo —
`node_modules`, a vendor directory, a virtualenv's `site-packages`. That's faster than a
machine-wide search, and it's guaranteed to be the exact version the lockfile resolves to, rather
than whatever unrelated checkout a `find` happens to turn up first.

## Scope

- Applies whenever the goal is reading a dependency's API or source, and the project's package
  manager can produce a local copy: `npm install`, `pip install`, `bundle install`, `go mod
  download`, etc.
- Reserve a filesystem-wide search for cases where the package manager can't produce a local copy
  at all.
- Doesn't apply once a dependency is already installed or vendored — read it from where it already
  lives.
