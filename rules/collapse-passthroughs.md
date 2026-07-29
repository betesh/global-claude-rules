# Collapse pass-throughs after refactor

_Delete no-op wrappers, rename-only vars, and import-to-export barrels in the same change set that creates them._

When a refactor leaves a no-op wrapper, rename, or barrel re-export, remove it in the same change set. Prefer updating callers over keeping a permanent alias.

## Pass-through functions

If a function's body only forwards to another function (same arguments, same return), **delete the wrapper** and update callers to call the underlying function.

```js
// ❌ BAD — leftover after behavior was removed / moved
export function wordsFromSpacedText(text) {
  return splitWords(text);
}

// ✅ GOOD — callers import and use splitWords
```

This includes rename wrappers (`foo` that only calls `bar`), even when the old name was once meaningful.

Keep a thin function only when it still adds behavior: composition of multiple steps, a meaningful bound default, or a **documented** stable public API that must not rename yet. Prefer updating callers.

## Import-to-export (barrel leftovers)

If a refactor moves a symbol to another module or package, **do not** leave the old file as:

```js
// ❌ BAD — import only to re-export after ownership moved
import { bar } from 'foo';
export { bar };
```

Update callers to import from the new owner. The old module may still **import** the symbol for its own local use, but it must not re-export it solely as a pass-through.

```js
// ✅ GOOD — local use only; callers import from the owner
import { bar } from 'foo';

export function doStuffWithBar(text) {
  return doStuff(bar(text));
}
```

Intentional package-boundary entry shims (`export * from 'dependency/…'`) are fine when that file's **only** job is the boundary — not when leftover after moving helpers out of a kitchen-sink module.

## Rename-only variables

If a variable is only assigned from another name and then used in its place, **drop the alias** and use the original.

```js
// ❌ BAD
const target = letter;
if (letters[i] !== target) continue;

// ✅ GOOD
if (letters[i] !== letter) continue;
```

Do not invent a new name "for clarity" when the existing parameter or binding already is that value.

## Finding the callers

Use Grep for the symbol name across the repo before deciding a wrapper is load-bearing. "Something might import it" is not a reason to keep it — check.
