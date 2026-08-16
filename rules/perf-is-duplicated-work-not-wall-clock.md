# Performance is duplicated work, not wall clock

_A test suite's or slow path's wall-clock duration moves with whatever else is running on the
machine at the time — it isn't a stable enough number to tune against or to track in a committed
file._

Two runs of the same code, back to back, can differ just from another process competing for CPU.
Chasing that number down, or maintaining a timings/duration-estimate file that records it run over
run, ends up optimizing against machine load rather than against the code.

Ask instead what the code computes more than once — the usual reason something is slower than it
needs to be is redundant work (the same input scanned, parsed, or transformed twice on one path),
not raw throughput.

## Scope

Applies to test-suite runtime and other wall-clock timings used as an informal performance
indicator. Doesn't cover a deliberate benchmark captured under controlled, idle conditions and
recorded with those conditions stated — see `measure-before-recording.md` for that case.
