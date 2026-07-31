# Measure before you write a number down

_A number that lands in code, docs, or a plan must come from a run — taken under conditions that make it mean what it claims._

Anything durable carrying a number — a threshold in code, a limit in a README, a budget in a
plan — is read later as an established fact. Nobody re-derives it. The bar for writing it down is
therefore that you measured it, not that you reasoned your way to it.

## A prediction is not a finding

Reasoning about where a limit *should* fall is a hypothesis, and hypotheses are wrong by
multiples often enough that the habit does not survive contact with data. They are also wrong in
**shape**, not only in magnitude: you conclude a retry budget of 3 covers the observed flakiness,
measure, and find most failures come from one endpoint that never succeeds on retry — so the
budget was never the variable.

That second kind is the expensive one, because a plausible wrong shape gets built before anyone
checks it. When you catch one, say plainly that the measurement contradicted the prediction;
quietly replacing the number hides that the reasoning behind it was unreliable.

If a number must appear before it can be measured, mark it as the guess it is and write down what
would confirm it.

## Conditions are part of the measurement

- **A timing or benchmark baseline taken on a loaded machine records the load.** Regenerating a
  committed timings / estimates / snapshot file while other work runs writes that contention into
  the file, and every later reader inherits it. Regenerate when the machine is idle, and diff
  against the previous file before committing — a uniform shift across every entry is the load,
  not the code.
- **A limit read off generated input is a limit on generated input.** Synthetic cases run harsher
  or gentler than real ones in ways that do not cancel out, so treat a synthetic result as a
  bound and confirm the number on real input before it ships.
- Record what the conditions were, next to the number. A measurement whose setup is unstated
  cannot be reproduced or challenged, which makes it indistinguishable from a guess.

## Scope

Applies to thresholds and tuning constants, limits quoted in documentation, performance figures,
capacity and cost estimates, and committed baseline files. Related: `run-focused-tests.md` — do
not report a test as passing that you did not run.
