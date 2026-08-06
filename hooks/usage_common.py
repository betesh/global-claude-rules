"""Shared machinery for the usage-window hooks.

Three entry points import this: usage_report.py (SessionStart — reports the
window and logs its boundary), usage_gate.py (UserPromptSubmit — decides
whether a prompt is worth sending), and checkpoint_stop.py (Stop — nudges a
checkpoint once context grows large without the session ever going idle). All
read the same two sources:

  usage/events.jsonl   what agents have observed — window starts and the
                       percentages the user reported
  <config>/projects/*/*.jsonl   session transcripts, whose per-request
                       `message.usage` counts measure what was actually sent

Tokens alone cannot say how much of the window is gone; a reported percentage is
what converts them. So callers print tokens always, and a percentage estimate
only once a `usage-report` event exists to calibrate against.

The window is exactly five hours. A reported renewal therefore fixes when it
started, by subtraction, more precisely than the event log can — override the
length with CLAUDE_USAGE_WINDOW_MINUTES. Renewal is always the start plus that
length: nothing here waits on a refusal to be observed, because a refusal
already cost the request it reported on, and one was never once recorded.
"""

import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

WINDOW = timedelta(minutes=int(os.environ.get("CLAUDE_USAGE_WINDOW_MINUTES", "300")))
TOKEN_FIELDS = (
    ("in", "input_tokens"),
    ("cache-write", "cache_creation_input_tokens"),
    ("cache-read", "cache_read_input_tokens"),
    ("out", "output_tokens"),
)

# List-price ratios relative to base input, applied when weighting spend for the calibration
# fit and the gate math below. A guess, not a measurement of what this account's cap actually
# charges per token type — but backtested across four observed windows (usage/notes.md's
# calibration section): fitting on tokens weighted this way tracks both held-out readings and
# each window's confirmed true per_pct consistently better than counting every token type flat.
TOKEN_WEIGHTS = {"in": 1.0, "cache-write": 1.25, "cache-read": 0.1, "out": 5.0}


def weighted_sum(counts):
    return sum(counts[name] * TOKEN_WEIGHTS[name] for name in counts)


REPO_DIR = os.environ["REPO_DIR"]
EVENTS_PATH = os.path.join(REPO_DIR, "usage", "events.jsonl")
CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")

now = datetime.now().astimezone()

# The estimate at which the gate stops letting requests through. Not 100: the
# last points of a window are worth less than the cost of discovering the
# ceiling by being refused, and the estimate carries a percentage point or two
# of slack.
GATE_AT_PCT = float(os.environ.get("CLAUDE_USAGE_GATE_PCT", "99"))

# Below this idle gap the prompt cache is confirmed still warm (a 53.8-minute
# gap left cache-read intact); at or above it every observed gap has come back
# with cache-read reset and a cache-write ≈ the whole conversation (three
# sessions, independently, plus two more from the same idle stretch: 141.3 and
# 146.3 minutes). The true crossing is somewhere below this; narrower brackets
# go in usage/notes.md as they're observed.
CACHE_TTL_MINUTES = float(os.environ.get("CLAUDE_CACHE_TTL_MINUTES", "141"))

# Context size at which a session idle past the TTL above is asked to clear.
# Still a guess: two genuine TTL crossings measured directly from transcripts
# (141 and 146-minute idle gaps) carried 231,467 and 71,903 tokens — both
# comfortably above this default, so it isn't contradicted, but nothing
# measured yet sits near the actual knee below which clearing saves less than
# the interruption costs. What would settle it is the distribution of
# carried-in sizes from `usage/context-cost.py` at real TTL crossings.
CARRY_AT = int(os.environ.get("CLAUDE_CARRIED_CONTEXT_TOKENS", "50000"))


def hook_payload():
    """The JSON the harness pipes to a hook: `session_id`, `transcript_path`, …

    Empty when the script is run by hand, so every use of it stays optional.
    """
    if sys.stdin.isatty():
        return {}
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_time(value):
    """Parses local ISO timestamps with a numeric UTC offset (how the log
    itself writes `t`) and UTC timestamps with a trailing "Z" (how transcripts
    always write theirs, regardless of the log's own format)."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def stamp(when):
    """Local wall-clock, regardless of whether `when` came from a local-offset
    log entry or a UTC transcript timestamp."""
    return when.astimezone().isoformat(timespec="minutes")


def stamp_seconds(when):
    """Full precision, for times another agent will compute a wait from."""
    return when.astimezone().isoformat(timespec="seconds")


def duration(delta):
    minutes = round(delta.total_seconds() / 60)
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    if minutes < 60:
        return f"{sign}{minutes}m"
    return f"{sign}{minutes // 60}h{minutes % 60:02d}m"


def read_events():
    events = []
    try:
        with open(EVENTS_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn concurrent append; the rest of the log stands
                when = parse_time(event.get("t"))
                if when:
                    event["_t"] = when
                    events.append(event)
    except OSError:
        return []
    events.sort(key=lambda e: e["_t"])
    return events


def logged_window_start(events):
    """The window start asserted by the most recently written boundary line.

    Only that one line is consulted, and it carries the start it asserts in
    `startedT` rather than being dated by when it was written. Both halves matter,
    because the log is append-only and can never be pruned.
    """
    for event in reversed(events):  # read_events sorts by write time
        if event.get("kind") == "renewed":
            return parse_time(event.get("startedT")) or event["_t"]
    return None


def scan_compact_attempts(since):
    """Timestamps of every `/compact` invocation since `since`, successful or not.

    Neither outcome leaves a token count anywhere: a failed attempt ends in a
    system/local_command error with no `usage` field, and a successful one is
    replaced by the isCompactSummary line, which also carries none. Both still
    reach the API — a failed one can spend real minutes, and real tokens,
    ingesting the prior context before erroring out — so a boundary search that
    only looks at `usage` lines can miss the request that actually opened a
    window. This exists to hand find_window_start() that timestamp too.
    """
    since_prefix = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    attempts = []
    pattern = os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl")
    for path in glob.glob(pattern):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < since:
                continue
            with open(path, errors="replace") as f:
                for line in f:
                    if '"/compact"' not in line:
                        continue
                    mark = line.find('"timestamp":"')
                    if mark != -1 and line[mark + 13:mark + 32] < since_prefix:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") != "user":
                        continue
                    message = entry.get("message")
                    if not isinstance(message, dict) or message.get("content") != "/compact":
                        continue
                    when = parse_time(entry.get("timestamp"))
                    if when and when >= since:
                        attempts.append(when)
        except OSError:
            continue
    return attempts


def find_window_start(events):
    """(start, confirmed) for the window now open, or (None, True) when none is.

    Three cases, and the middle one is why this is not just a freshness check:

    - the logged start is younger than a window: that window is still running,
      confirmed by definition — it was itself derived from real evidence.
    - it is older: at least one window has turned over since. The one now open
      began at the first request after the old one expired, and that timestamp is
      in the transcripts — so roll forward through them a window at a time rather
      than stamping the start as now. Stamping now is what makes a window look
      short, by however long it took a session to start and notice. A `/compact`
      counts as a request here too (see scan_compact_attempts), since it reaches
      the API whether or not it leaves a token count behind.
    - no boundary line at all: nothing anchors the roll-forward, because traffic
      reaching back past wherever the scan begins gives an arbitrary phase. The
      caller treats now as the start and says so.

    The roll-forward can still find nothing: a gate hook runs before the prompt
    that triggered it is written to the transcript, so the request that actually
    crossed the boundary is invisible to the scan that would have found it. When
    that happens, `confirmed` comes back False and the caller must not persist
    the result — logged + WINDOW is only an arithmetic placeholder, and the next
    call (this session's next prompt, or another session's) should roll forward
    again with whatever the transcripts have gained by then, rather than treat
    the placeholder as settled for the rest of the window's life.
    """
    logged = logged_window_start(events)
    if logged is None:
        return None, True
    if now - logged < WINDOW:
        return logged, True

    requests, _ = scan_transcripts(logged + WINDOW)
    candidates = [when for when, _, _ in requests.values()] + scan_compact_attempts(logged + WINDOW)
    start, cursor = None, None
    for when in sorted(candidates):
        if cursor is None or when >= cursor:
            start, cursor = when, when + WINDOW
    confirmed = start is not None
    if start is None:
        start = logged + WINDOW
    return (start, confirmed) if now - start < WINDOW else (None, True)


def _ppid(pid):
    try:
        stat = open(f"/proc/{pid}/stat").read()
    except OSError:
        return None
    # comm (2nd field) is parenthesized and can itself contain spaces, so split
    # after its closing paren rather than by position from the start.
    fields = stat.rsplit(")", 1)[-1].split()
    try:
        return int(fields[1])
    except (IndexError, ValueError):
        return None


def claude_pid():
    """The pid of the `claude` process this hook is running under, or None.

    session_id is not stable across `/clear` — confirmed empirically, a
    checkpoint-nudged event and the cleared event that followed it seconds
    later carried two different session ids — but the terminal's underlying
    process doesn't change, so its pid is what links a nudge back to whatever
    clear follows it. Walks the hook's own ancestry (it runs as a child of a
    shell wrapper, itself a child of `claude`) rather than trusting a fixed
    number of hops, since that depth isn't guaranteed to stay the same.
    """
    pid = os.getpid()
    for _ in range(12):
        ppid = _ppid(pid)
        if not ppid:
            return None
        try:
            comm = open(f"/proc/{ppid}/comm").read().strip()
        except OSError:
            return None
        if comm == "claude":
            return ppid
        pid = ppid
    return None


def append_event(session_id, event):
    """Add one line to the shared log. Append only: concurrent writers share it.

    Keys are ordered t, kind, session, then whatever else the event carries — so
    rows line up when scanning the file by eye.
    """
    ordered = {}
    ordered["t"] = stamp_seconds(now)
    ordered["kind"] = event.get("kind")
    if session_id:
        ordered["session"] = session_id
    ordered.update((k, v) for k, v in event.items() if k != "kind")
    try:
        os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
        with open(EVENTS_PATH, "a") as f:
            f.write(json.dumps(ordered) + "\n")
    except OSError:
        pass


def log_boundary(session_id, started):
    """Record when the window now open began, so the next session reads it.

    Written whenever the start was worked out from something other than the log —
    a reported renewal, or a roll-forward through the transcripts — which is what
    keeps the log current without anyone pruning it. The window it names is in
    `startedT`; `t` stays the write time, and the two are rarely the same.
    """
    append_event(session_id, {"kind": "renewed", "startedT": stamp_seconds(started)})


def scan_transcripts(since):
    """Per-request token totals from every transcript touched since `since`.

    One request writes many transcript lines as it streams, all sharing a
    requestId and each carrying the running usage totals — so the last line for
    a requestId is that request's true cost, and earlier ones must not be added
    to it.
    """
    requests = {}
    sessions = set()
    # Transcript lines are long, so old ones are rejected on the raw text —
    # ISO-8601 sorts lexicographically — rather than by parsing each one.
    # Transcript timestamps are always UTC, regardless of what `since` is in.
    since_prefix = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    # A subagent (Agent tool) writes its own transcript one level deeper than a
    # session's own, at <session>/subagents/agent-*.jsonl — real spend against
    # the same account, invisible to every total here until both patterns are
    # scanned (usage/notes.md: confirmed by direct filesystem check, 2026-08-04).
    patterns = [
        os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl"),
        os.path.join(CONFIG_DIR, "projects", "*", "*", "subagents", "*.jsonl"),
    ]
    for path in (p for pattern in patterns for p in glob.glob(pattern)):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < since:
                continue  # every line in it predates the window
            with open(path, errors="replace") as f:
                for line in f:
                    if '"usage"' not in line:
                        continue
                    mark = line.find('"timestamp":"')
                    if mark != -1 and line[mark + 13:mark + 32] < since_prefix:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    usage = (entry.get("message") or {}).get("usage")
                    when = parse_time(entry.get("timestamp"))
                    if not isinstance(usage, dict) or not when or when < since:
                        continue
                    key = entry.get("requestId") or entry.get("uuid")
                    counts = {name: usage.get(field) or 0 for name, field in TOKEN_FIELDS}
                    requests[key] = (when, counts, (entry.get("message") or {}).get("model"))
                    sessions.add(path)
        except OSError:
            continue
    return requests, sessions


def tokens_through(requests, cutoff=None, weighted=False):
    total = 0
    for when, counts, _ in requests.values():
        if cutoff is None or when <= cutoff:
            total += weighted_sum(counts) if weighted else sum(counts.values())
    return total


def tokens_per_minute(requests, since, until, weighted=False):
    """Token rate over a span, or 0 when the span is too short to mean anything.

    Averaging over the whole window instead answers a question nobody asked: it
    includes agents that have since been cleared, so it keeps projecting a burn
    rate that stopped. A span shorter than this is mostly quantisation noise from
    however requests happened to land in it.
    """
    minutes = (until - since).total_seconds() / 60
    if minutes < 3:
        return 0
    values = (
        (weighted_sum(counts) if weighted else sum(counts.values()))
        for when, counts, _ in requests.values() if since < when <= until
    )
    total = sum(values)
    return total / minutes if total else 0


def calibrate(reports, requests):
    """Fit `pct = intercept + weighted_tokens / per_pct` over the window's reports.

    Least squares across every reading, not the first-to-last delta: with three
    or more readings the fit is over-determined, so one mistyped percentage bends
    the line instead of defining it.

    The intercept is the point of it. Spend that the scan cannot see — traffic
    before the window start it inferred, or transcripts outside the config dir —
    is a constant offset, and forcing the line through the origin pushes that
    offset into the slope, which is what makes a ratio fitted from one report
    disagree with the delta by a factor of two.

    Fits on `weighted_sum` tokens rather than a flat count — see TOKEN_WEIGHTS above.

    Returns `(per_pct, intercept, n)`; `n` is how many readings backed it, and
    `n >= 2` is what separates a measured slope from a single-point guess.
    """
    points = [(tokens_through(requests, r["_t"], weighted=True), r["pct"]) for r in reports]
    if len({t for t, _ in points}) >= 2:
        n = len(points)
        sx = sum(t for t, _ in points)
        sy = sum(p for _, p in points)
        sxy = sum(t * p for t, p in points)
        sxx = sum(t * t for t, _ in points)
        denominator = n * sxx - sx * sx
        if denominator:
            slope = (n * sxy - sx * sy) / denominator
            if slope > 0:
                return 1 / slope, (sy - slope * sx) / n, n
    if points:
        tokens, pct = points[-1]
        if pct > 0 and tokens > 0:
            return tokens / pct, 0.0, 1
    return 0, 0.0, 0


def window_state(events):
    """Everything derived from the log and the transcripts, computed once.

    Every mode reads the same numbers from here so that a gate decision and the
    line explaining it can never disagree.
    """
    # The window is exactly WINDOW long, so a reported renewal fixes its start by
    # subtraction — and does it better than the log can. A `renewed` event is
    # written when an agent noticed credit was back, which trails the renewal
    # itself by however long that took, and every minute of that lag shortens the
    # window the hook thinks it is in.
    renews = basis = None
    for event in reversed(events):
        if event.get("kind") == "usage-report" and isinstance(event.get("renewsInMin"), (int, float)):
            candidate = event["_t"] + timedelta(minutes=event["renewsInMin"])
            if candidate > now:
                renews = candidate
                basis = f"reported at {stamp(event['_t'])}"
                break

    if renews:
        window_start = renews - WINDOW
        opened = False
        confirmed = True
        source = "derived from a reported renewal"
    else:
        window_start, confirmed = find_window_start(events)
        opened = window_start is None
        if opened:
            window_start = now
            confirmed = True
        source = "this session's start, with nothing in the log to place it" if opened \
            else "the first request after the previous window expired"
        renews = window_start + WINDOW
        basis = f"no renewal reported in this window; {duration(WINDOW)} after its first request"

    # Worth writing down unless the log already says the same thing. The minutes
    # of tolerance are because a start derived from a reported renewal is only as
    # precise as the minute the user read off, and re-logging on that jitter would
    # add a line per session for no new information. Never persists an
    # unconfirmed guess: doing so would freeze it in as "known" and stop any
    # later call from ever rolling forward again within this window's life.
    known = logged_window_start(events)
    unlogged = confirmed and (known is None or abs((window_start - known).total_seconds()) > 120)

    requests, sessions = scan_transcripts(window_start)
    totals = {name: 0 for name, _ in TOKEN_FIELDS}
    by_model = {}
    for _, counts, model in requests.values():
        for name in totals:
            totals[name] += counts[name]
        by_model[model] = by_model.get(model, 0) + sum(counts.values())

    reports = [
        e for e in events
        if e.get("kind") == "usage-report" and e["_t"] >= window_start
        and isinstance(e.get("pct"), (int, float))
    ]
    last = reports[-1] if reports else None
    per_pct, intercept, backing = calibrate(reports, requests)

    spent = sum(totals.values())
    weighted_spent = tokens_through(requests, weighted=True)
    estimate = intercept + weighted_spent / per_pct if per_pct else None

    return {
        "window_start": window_start, "opened": opened, "unlogged": unlogged,
        "source": source, "requests": requests,
        "sessions": sessions, "totals": totals, "by_model": by_model, "spent": spent,
        "weighted_spent": weighted_spent,
        "reports": reports, "last": last, "per_pct": per_pct, "intercept": intercept,
        "backing": backing, "estimate": estimate, "renews": renews, "basis": basis,
    }


def gate_reason(state):
    """Why a request must not be sent, or None to let it through.

    Shared by usage_gate.py (a prompt) and usage_compact_gate.py (a /compact):
    both spend real tokens against the same window, and a /compact can spend
    them even when it fails (usage/notes.md: a failed one spent ~4 minutes
    ingesting ~434K tokens before a 529). The fitted estimate is the only
    ground, and it is not a trustworthy one — it has been wrong by a factor of
    two in this repo's own measurements, and refusing on a bad one idles every
    agent on the machine until the window turns over, which is the more
    expensive mistake because nobody notices it. So it blocks only when a
    measured slope stands behind it (two or more readings) and the renewal it
    would wait for is a time the log actually knows.
    """
    estimate, last = state["estimate"], state["last"]
    if estimate is None or estimate < GATE_AT_PCT or state["backing"] < 2:
        return None
    if not (state["renews"] > now):
        return None
    return (
        f"the window is ~{min(estimate, 100):.0f}% spent — {state['per_pct']:,.0f} weighted-tok/% "
        f"fitted on {state['backing']} readings, last the {last['pct']}% at {stamp(last['_t'])}",
        state["renews"],
    )


def session_carry(path):
    """(context now, weighted context now, timestamp of the last request,
    timestamp of the first) for one transcript, or None when it has no real
    request at all.

    Context is what the newest request sent — input plus both cache figures.
    Output tokens are not context: they are produced by the request rather than
    carried into it, and they reach the next one inside its cached prefix.
    The weighted figure applies TOKEN_WEIGHTS, so it can be compared against a
    weighted per-pct budget (calibrate() above) without mixing units.

    A `/compact` rewrites everything before it into one summary turn (marked
    `isCompactSummary` on a plain user message, no `usage` of its own), so a
    pre-compact request's usage no longer says what the next request will
    send. Context resets to 0 at that line rather than falling back to the
    last pre-compact figure — there is no measurement of the post-compact
    size until a real request follows it.
    """
    first = last = None
    context = 0
    weighted_context = 0.0
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if '"usage"' not in line and '"isCompactSummary"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                when = parse_time(entry.get("timestamp"))
                if entry.get("isCompactSummary"):
                    if when:
                        last = when
                    context, weighted_context = 0, 0.0
                    continue
                usage = (entry.get("message") or {}).get("usage")
                if entry.get("type") != "assistant" or not isinstance(usage, dict) or not when:
                    continue
                in_tokens = usage.get("input_tokens") or 0
                cache_write = usage.get("cache_creation_input_tokens") or 0
                cache_read = usage.get("cache_read_input_tokens") or 0
                request_context = in_tokens + cache_write + cache_read
                request_weighted = (
                    in_tokens * TOKEN_WEIGHTS["in"]
                    + cache_write * TOKEN_WEIGHTS["cache-write"]
                    + cache_read * TOKEN_WEIGHTS["cache-read"]
                )
                # A synthetic assistant message carries an all-zero usage block and is
                # usually the first line in a transcript — counting it as a request
                # makes a session look like it started long before its real first one.
                if not request_context and not (usage.get("output_tokens") or 0):
                    continue
                if first is None or when < first:
                    first = when
                if last is None or when >= last:
                    last = when
                    context = request_context
                    weighted_context = request_weighted
    except OSError:
        return None
    return (context, weighted_context, last, first) if first else None
