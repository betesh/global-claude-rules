#!/usr/bin/env python3
"""Summarize the shared credit window for SessionStart context.

Invoked by usage-window.sh with REPO_DIR set. Two sources, both local:

  usage/events.jsonl   what agents have observed — window starts, limit hits,
                       percentages the user reported
  <config>/projects/*/*.jsonl   session transcripts, whose per-request
                       `message.usage` counts measure what was actually sent

Tokens alone cannot say how much of the window is gone; a reported percentage is
what converts them. So this prints tokens always, and a percentage estimate only
once a `usage-report` event exists to calibrate against.

The window is exactly five hours. A reported renewal therefore fixes when it
started, by subtraction, more precisely than the event log can — override the
length with CLAUDE_USAGE_WINDOW_MINUTES.

Reads the hook's JSON payload on stdin for `session_id`: several agents append to
one log, so every line it writes is tagged with the session that wrote it, and it
tells the model that id so its own appends carry the same tag.

With `--sleep-seconds` it prints a number instead: how long a launcher should
wait before starting an agent at all, given what the log already says about the
window. That answer is for code, not for the model — deciding to wait costs a
request once a session is running, and by then the wait is what you were trying
to avoid.
"""

import argparse
import glob
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

WINDOW = timedelta(minutes=int(os.environ.get("CLAUDE_USAGE_WINDOW_MINUTES", "300")))
TOKEN_FIELDS = (
    ("in", "input_tokens"),
    ("cache-write", "cache_creation_input_tokens"),
    ("cache-read", "cache_read_input_tokens"),
    ("out", "output_tokens"),
)

REPO_DIR = os.environ["REPO_DIR"]
EVENTS_PATH = os.path.join(REPO_DIR, "usage", "events.jsonl")
CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")

now = datetime.now(timezone.utc)


def hook_session_id():
    """This session's id, from the JSON the harness pipes to a SessionStart hook.

    Absent when the script is run by hand, so every use of it stays optional.
    """
    if sys.stdin.isatty():
        return None
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, ValueError):
        return None
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    return session_id if isinstance(session_id, str) and session_id else None


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize the shared credit window.")
    parser.add_argument(
        "--sleep-seconds",
        action="store_true",
        help="print how many seconds to wait before starting an agent, and nothing else",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="refuse the request when the window is spent; otherwise print one estimate line",
    )
    parser.add_argument("--session", help="session id to tag anything this run appends to the log")
    return parser.parse_args()


ARGS = parse_args()
# stdin is the hook payload only when the harness invoked us; a launcher passes --session.
SESSION_ID = ARGS.session or (None if ARGS.sleep_seconds else hook_session_id())

# The estimate at which --gate stops letting requests through. Not 100: the last
# points of a window are worth less than the cost of discovering the ceiling by
# being refused, and the estimate carries a percentage point or two of slack.
GATE_AT_PCT = float(os.environ.get("CLAUDE_USAGE_GATE_PCT", "97"))


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def stamp(when):
    return when.strftime("%Y-%m-%dT%H:%MZ")


def stamp_seconds(when):
    """Full precision, for times another agent will compute a wait from."""
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def newest(events, kind):
    for event in reversed(events):
        if event.get("kind") == kind:
            return event
    return None


def credit_returned_after(events, when):
    """True when something logged after `when` shows requests are being served again.

    A limit-hit or a declared sleep names a deadline to wait until, but credit
    can come back before it — a window may renew earlier than the wait a refusal
    reported. A later `renewed`, or a reported percentage below 100, is direct
    evidence the account is serving. Without this check one stale entry keeps
    every agent idle until its own deadline passes, which is the expensive
    direction to be wrong in: the window is open and nobody is using it.
    """
    for event in reversed(events):
        if event["_t"] <= when:
            return False
        if event.get("kind") == "renewed":
            return True
        pct = event.get("pct")
        if event.get("kind") == "usage-report" and isinstance(pct, (int, float)) and pct < 100:
            return True
    return False


def standing_limit_hit(events):
    """The newest limit-hit, unless something later showed credit came back."""
    hit = newest(events, "limit-hit")
    if hit and credit_returned_after(events, hit["_t"]):
        return None
    return hit


def find_window_start(events):
    """Earliest evidence of a served request since the last window ended.

    Returns None when no window is open. A `renewed` counts alongside a
    `first-request`: it is logged precisely because a request succeeded, so it
    marks a window that is already running. Without it, a session that renews
    mid-conversation reports the window as starting whenever the hook next runs,
    and silently drops every reading taken in between.
    """
    boundary = None
    limit_hit = standing_limit_hit(events)
    renewed = newest(events, "renewed")
    for candidate in (limit_hit and parse_time(limit_hit.get("resetAt")), renewed and renewed["_t"]):
        if candidate and (boundary is None or candidate > boundary):
            boundary = candidate

    starts = [
        e["_t"] for e in events
        if e.get("kind") in ("first-request", "renewed") and (boundary is None or e["_t"] >= boundary)
    ]
    if not starts:
        return None
    start = min(starts)
    return None if now - start >= WINDOW else start


def append_event(event):
    """Add one line to the shared log. Append only: concurrent writers share it."""
    event = {"t": stamp_seconds(now), **event}
    if SESSION_ID:
        event["session"] = SESSION_ID
    try:
        os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
        with open(EVENTS_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass


def log_first_request():
    append_event({"kind": "first-request", "note": "session start; logged by hook before any request"})


def pending_wait(events):
    """The time to wait until before starting an agent, or None to start now.

    Only events where someone already established that credit is gone count: a
    limit-hit whose reset has not passed, and a sleep another agent declared and
    is still serving. A percentage estimate is deliberately not grounds to wait
    — the calibration behind it has been wrong by multiples, and waiting out a
    window that is actually serving costs more than one refusal would.
    """
    waits = []
    limit_hit = standing_limit_hit(events)
    if limit_hit:
        reset_at = parse_time(limit_hit.get("resetAt"))
        if reset_at and reset_at > now:
            waits.append((reset_at, f"limit-hit at {stamp(limit_hit['_t'])} puts renewal at {stamp(reset_at)}"))

    declared = newest(events, "sleep")
    if declared and not credit_returned_after(events, declared["_t"]):
        until = parse_time(declared.get("untilT"))
        if until and until > now:
            who = declared.get("session") or "an untagged session"
            waits.append((until, f"{who} is already waiting until {stamp(until)}"))

    return max(waits, default=None)


def report_sleep(events):
    """Print seconds for a launcher to sleep; the reason goes to stderr."""
    wait = pending_wait(events)
    if wait is None:
        print(0)
        return
    until, reason = wait
    # A few tens of seconds of jitter so agents released by the same renewal do
    # not all race for the first request.
    until += timedelta(seconds=random.randint(0, 60))
    print(max(0, round((until - now).total_seconds())))
    append_event(
        {"kind": "sleep", "untilT": stamp_seconds(until), "reason": f"{reason}; waiting before launch"}
    )
    print(f"credit is out: {reason}; waiting until {stamp(until)}", file=sys.stderr)


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
    since_prefix = since.strftime("%Y-%m-%dT%H:%M:%S")
    pattern = os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl")
    for path in glob.glob(pattern):
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


def tokens_through(requests, cutoff=None):
    total = 0
    for when, counts, _ in requests.values():
        if cutoff is None or when <= cutoff:
            total += sum(counts.values())
    return total


def tokens_per_minute(requests, since, until):
    """Token rate over a span, or 0 when the span is too short to mean anything.

    Averaging over the whole window instead answers a question nobody asked: it
    includes agents that have since been cleared, so it keeps projecting a burn
    rate that stopped. A span shorter than this is mostly quantisation noise from
    however requests happened to land in it.
    """
    minutes = (until - since).total_seconds() / 60
    if minutes < 3:
        return 0
    total = sum(sum(counts.values()) for when, counts, _ in requests.values() if since < when <= until)
    return total / minutes if total else 0


def calibrate(reports, requests):
    """Fit `pct = intercept + tokens / per_pct` over the window's reports.

    Least squares across every reading, not the first-to-last delta: with three
    or more readings the fit is over-determined, so one mistyped percentage bends
    the line instead of defining it.

    The intercept is the point of it. Spend that the scan cannot see — traffic
    before the window start it inferred, or transcripts outside the config dir —
    is a constant offset, and forcing the line through the origin pushes that
    offset into the slope, which is what makes a ratio fitted from one report
    disagree with the delta by a factor of two.

    Returns `(per_pct, intercept, n)`; `n` is how many readings backed it, and
    `n >= 2` is what separates a measured slope from a single-point guess.
    """
    points = [(tokens_through(requests, r["_t"]), r["pct"]) for r in reports]
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
    else:
        window_start = find_window_start(events)
        opened = window_start is None
        if opened:
            window_start = now
        renews = window_start + WINDOW
        basis = f"no renewal reported in this window; {duration(WINDOW)} after its first request"

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
    estimate = intercept + spent / per_pct if per_pct else None

    return {
        "window_start": window_start, "opened": opened, "requests": requests,
        "sessions": sessions, "totals": totals, "by_model": by_model, "spent": spent,
        "reports": reports, "last": last, "per_pct": per_pct, "intercept": intercept,
        "backing": backing, "estimate": estimate, "renews": renews, "basis": basis,
    }


def gate_reason(events, state):
    """Why this request must not be sent, or None to let it through.

    Two independent grounds, and they are not equally trustworthy:

    An unexpired `limit-hit` is an observation — a request was actually refused
    — so it blocks on its own.

    An estimate is not. It has been wrong by a factor of two in this repo's own
    measurements, and refusing on a bad one idles every agent on the machine
    until the window turns over, which is the more expensive mistake because
    nobody notices it. So the estimate only blocks when a measured slope stands
    behind it (two or more readings) and the renewal it would wait for is a time
    the log actually knows.
    """
    limit_hit = standing_limit_hit(events)
    if limit_hit:
        reset_at = parse_time(limit_hit.get("resetAt"))
        if reset_at and reset_at > now:
            return (
                f"a request was refused at {stamp(limit_hit['_t'])}, putting renewal at "
                f"{stamp(reset_at)} ({duration(reset_at - now)} from now)",
                reset_at,
            )

    estimate, last = state["estimate"], state["last"]
    if estimate is None or estimate < GATE_AT_PCT or state["backing"] < 2:
        return None
    if not (state["renews"] > now):
        return None
    return (
        f"the window is ~{min(estimate, 100):.0f}% spent — {state['per_pct']:,.0f} tokens/% "
        f"fitted on {state['backing']} readings, last the {last['pct']}% at {stamp(last['_t'])}",
        state["renews"],
    )


def run_gate(events):
    """Refuse a request outright when credit is gone, else describe the window.

    Exit 2 is what makes this autonomous: the harness drops the prompt before a
    request is sent, so an exhausted window costs nothing at all. Everything
    cheaper than this — a warning in context, a rule the model is asked to
    follow — still spends the request that discovers the window is empty.
    """
    state = window_state(events)
    reason = gate_reason(events, state)
    if reason:
        why, until = reason
        wait = until + timedelta(seconds=random.randint(0, 60))
        if not newest_sleep_covers(events, until):
            append_event({"kind": "sleep", "untilT": stamp_seconds(wait),
                          "reason": f"{why}; gated before the request was sent"})
        print(
            f"Credit is out: {why}. Not sending this request. The window renews at "
            f"{stamp(until)}, {duration(until - now)} from now — wait until then, or set "
            f"CLAUDE_USAGE_GATE_PCT above {GATE_AT_PCT:.0f} to override.",
            file=sys.stderr,
        )
        sys.exit(2)

    if state["estimate"] is not None:
        print(
            f"credit ~{min(state['estimate'], 100):.0f}% used "
            f"({state['spent']:,} tokens at {state['per_pct']:,.0f}/%, "
            f"{state['backing']} reading{'s' if state['backing'] != 1 else ''}), "
            f"renews {stamp(state['renews'])} in {duration(state['renews'] - now)}"
        )


def newest_sleep_covers(events, until):
    """True when a sleep already declared reaches this renewal, so one gated
    agent does not append a near-duplicate line on every prompt it blocks."""
    declared = newest(events, "sleep")
    if not declared or credit_returned_after(events, declared["_t"]):
        return False
    when = parse_time(declared.get("untilT"))
    return bool(when and when >= until - timedelta(minutes=5))


def main():
    events = read_events()
    if ARGS.sleep_seconds:
        report_sleep(events)
        return
    if ARGS.gate:
        run_gate(events)
        return

    out = []

    limit_hit = standing_limit_hit(events)
    reset_at = parse_time(limit_hit.get("resetAt")) if limit_hit else None
    if reset_at and reset_at > now:
        print(
            f"CREDIT IS OUT — a limit-hit logged at {stamp(limit_hit['_t'])} puts renewal at "
            f"{stamp(reset_at)}, {duration(reset_at - now)} from now. Another agent already paid "
            "for this information; do not rediscover it. Start no work: say you are waiting until "
            "then and stop, or sleep in the background with a small random offset so concurrent "
            f"agents do not race the first request (see {REPO_DIR}/rules/usage-limits-and-context.md)."
        )
        return

    state = window_state(events)
    if state["opened"]:
        log_first_request()
    window_start = state["window_start"]
    opened = " (this session opened it)" if state["opened"] else ""
    requests, sessions = state["requests"], state["sessions"]
    totals, by_model, spent = state["totals"], state["by_model"], state["spent"]
    renews, basis = state["renews"], state["basis"]

    out.append(
        f"  window   started {stamp(window_start)}, {duration(now - window_start)} ago{opened}"
    )
    if renews > now:
        out.append(f"  renews   {stamp(renews)}, in {duration(renews - now)} ({basis})")
    else:
        out.append(
            f"  renews   {stamp(renews)} — that has passed, so the window should have reset "
            f"already ({basis}); the next request confirms it, so log a renewed event"
        )
    if requests:
        breakdown = ", ".join(f"{name} {totals[name]:,}" for name, _ in TOKEN_FIELDS)
        out.append(
            f"  spent    {spent:,} tokens over {len(requests)} requests in "
            f"{len(sessions)} session{'s' if len(sessions) != 1 else ''} ({breakdown})"
        )
        if len(by_model) > 1:
            mix = ", ".join(
                f"{model or 'unknown'} {count:,}"
                for model, count in sorted(by_model.items(), key=lambda kv: -kv[1])
            )
            out.append(f"  models   {mix} — models are not priced alike, so this total is a mix")
    else:
        out.append("  spent    no transcript traffic recorded in this window yet")

    last, per_pct = state["last"], state["per_pct"]

    if per_pct:
        estimate = state["estimate"]
        fitted = (
            f"fitted on {state['backing']} readings"
            if state["backing"] >= 2
            else f"from the single {last['pct']}% reading at {stamp(last['_t'])}, which cannot "
                 "separate spend the scan misses from the rate — treat it as a guess"
        )
        line = (
            f"  estimate ~{min(estimate, 100):.0f}% used, {per_pct:,.0f} tokens/% {fitted}"
        )
        if estimate >= 100:
            line += "; that calibration says the window is already spent — expect a refusal, and "
            line += "ask for a fresh reading before trusting it"
        else:
            # Prefer the rate since the last reading: it reflects how many agents
            # are running now. Fall back to the window average only when that span
            # is too short, and say so, because it embeds bursts already over.
            rate = tokens_per_minute(requests, last["_t"], now)
            span = f"the {duration(now - last['_t'])} since that reading"
            if not rate:
                elapsed = (now - window_start).total_seconds() / 60
                rate = spent / elapsed if elapsed > 0 else 0
                span = "the whole window, which still counts agents that have since stopped"
            if rate:
                empty = now + timedelta(minutes=(100 - estimate) * per_pct / rate)
                verdict = "before renewal — pace or stop early" if empty < renews else "after renewal"
                line += f"; at the rate over {span}, credit runs out {stamp(empty)} ({verdict})"
        out.append(line)
    elif last:
        out.append(
            f"  estimate none — the {last['pct']}% reported at {stamp(last['_t'])} cannot be "
            "calibrated: no transcript traffic was recorded before it. A later report will fix this."
        )
    else:
        out.append(
            "  estimate none — tokens cannot be converted to a percentage until the user reports "
            'one. Ask for "X% used, renews in Y minutes" before any long unattended run, and log '
            "it as a usage-report event."
        )

    print("Shared credit window (computed by a SessionStart hook; no request was spent):")
    print("\n".join(out))
    tag = (
        f', tagged "session":"{SESSION_ID}" so a line can be traced back to the agent that wrote it'
        if SESSION_ID else ""
    )
    print(f"  log      {EVENTS_PATH} — append what you observe{tag}; conclusions go in usage/notes.md")


try:
    main()
except Exception:  # a session must never fail to start because of this hook
    sys.exit(0)
