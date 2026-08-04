# Chain a dependent shell step onto the one it needs

_When a shell command's only job is to consume the previous command's output, put both in one
call — command substitution or `&&`, not a second round trip._

Each tool call resends the whole conversation so far, so a second command that adds no new
reasoning — it only needed a value or a pass/fail from the first — is a full-context resend paid
for nothing but plumbing.

```bash
# ❌ BAD — the second call exists only to consume the first's stdout
ls -t backups/*.tar.gz | head -1
tar tzf backups/2024-03-04.tar.gz     # path pasted in from the previous output

# ✅ GOOD — one call
tar tzf "$(ls -t backups/*.tar.gz | head -1)"
```

```bash
# ❌ BAD — a check, then a separate action gated on it
grep -q READY status.log
mv build/out build/release

# ✅ GOOD
grep -q READY status.log && mv build/out build/release
```

A short pre-commit sequence — verify, stage, commit — is the same shape: each step's command is
already fully known before the previous one returns, so `check && git add PATHS && git commit -F -
<<EOF ... EOF` is one call, not three.

## Scope

Applies only when the next command is already fully determined — extracting a value, or branching
on an exit code — not when the output has to be read and actually reasoned about before deciding
what to do next. Inspecting a file to decide what to change is a real dependency; each step is its
own call and this rule doesn't apply. When genuinely independent steps just happen to run one after
another, that's `no-interactive-editing.md`'s territory instead — batch them in one message rather
than chaining them in shell.
