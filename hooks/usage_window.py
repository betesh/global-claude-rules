#!/usr/bin/env python3
"""Summarize the shared credit window for SessionStart context.

Invoked by usage-window.sh with REPO_DIR set. Two sources, both local:

  usage/events.jsonl   what agents have observed — window starts and the
                       percentages the user reported
  <config>/projects/*/*.jsonl   session transcripts, whose per-request
                       `message.usage` counts measure what was actually sent

Tokens alone cannot say how much of the window is gone; a reported percentage is
what converts them. So this prints tokens always, and a percentage estimate only
once a `usage-report` event exists to calibrate against.

The window is exactly five hours. A reported renewal therefore fixes when it
started, by subtraction, more precisely than the event log can — override the
length with CLAUDE_USAGE_WINDOW_MINUTES. Renewal is always the start plus that
length: nothing here waits on a refusal to be observed, because a refusal
already cost the request it reported on, and one was never once recorded.

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

# How far past a derived renewal to aim when waiting one out. See wake_at.
WAKE_MARGIN = timedelta(seconds=60)


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


def logged_window_start(events):
    """The window start asserted by the most recently written boundary line.

    Only that one line is consulted, and it carries the start it asserts in
    `startedT` rather than being dated by when it was written. Both halves matter,
    because the log is append-only and can never be pruned:

    - Reading the *earliest* boundary line instead pins the start to the first one
      ever written. Once that is five hours old every session sees an expired
      window, declares it opened one itself, and appends another line that will
      likewise never be read — recoverable only by emptying the file by hand.
    - Dating a line by when it was written makes a stale line from an hour into
      some past window outrank an accurate one, since it is the later timestamp.
      A line that says what it means is inert once superseded.

    Lines written before `startedT` existed fall back to their write time, which
    is what they meant.
    """
    for event in reversed(events):  # read_events sorts by write time
        if event.get("kind") in ("first-request", "renewed"):
            return parse_time(event.get("startedT")) or event["_t"]
    return None


def find_window_start(events):
    """When the window now open began, or None when no window is open.

    Three cases, and the middle one is why this is not just a freshness check:

    - the logged start is younger than a window: that window is still running.
    - it is older: at least one window has turned over since. The one now open
      began at the first request after the old one expired, and that timestamp is
      in the transcripts — so roll forward through them a window at a time rather
      than stamping the start as now. Stamping now is what makes a window look
      short, by however long it took a session to start and notice.
    - no boundary line at all: nothing anchors the roll-forward, because traffic
      reaching back past wherever the scan begins gives an arbitrary phase. The
      caller treats now as the start and says so.
    """
    logged = logged_window_start(events)
    if logged is None:
        return None
    if now - logged < WINDOW:
        return logged

    requests, _ = scan_transcripts(logged + WINDOW)
    start, cursor = None, None
    for when in sorted(when for when, _, _ in requests.values()):
        if cursor is None or when >= cursor:
            start, cursor = when, when + WINDOW
    return start if start and now - start < WINDOW else None


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


def log_boundary(started, note):
    """Record when the window now open began, so the next session reads it.

    Written whenever the start was worked out from something other than the log —
    a reported renewal, or a roll-forward through the transcripts — which is what
    keeps the log current without anyone pruning it. The window it names is in
    `startedT`; `t` stays the write time, and the two are rarely the same.
    """
    append_event({"kind": "renewed", "startedT": stamp_seconds(started), "note": note})


def wake_at(renews):
    """When to come back after a window that is spent: renewal, plus slack.

    The renewal time is derived — start plus a fixed length — so a launcher that
    aims exactly at it lands on the boundary and can be refused by a clock a
    minute off. A flat margin crosses it, and a few tens of seconds of jitter on
    top keep agents released by the same renewal from racing the first request.
    """
    return renews + WAKE_MARGIN + timedelta(seconds=random.randint(0, 60))


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
        source = "derived from a reported renewal"
    else:
        window_start = find_window_start(events)
        opened = window_start is None
        if opened:
            window_start = now
        source = "this session's start, with nothing in the log to place it" if opened \
            else "the first request after the previous window expired"
        renews = window_start + WINDOW
        basis = f"no renewal reported in this window; {duration(WINDOW)} after its first request"

    # Worth writing down unless the log already says the same thing. The minutes
    # of tolerance are because a start derived from a reported renewal is only as
    # precise as the minute the user read off, and re-logging on that jitter would
    # add a line per session for no new information.
    known = logged_window_start(events)
    unlogged = known is None or abs((window_start - known).total_seconds()) > 120

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
        "window_start": window_start, "opened": opened, "unlogged": unlogged,
        "source": source, "requests": requests,
        "sessions": sessions, "totals": totals, "by_model": by_model, "spent": spent,
        "reports": reports, "last": last, "per_pct": per_pct, "intercept": intercept,
        "backing": backing, "estimate": estimate, "renews": renews, "basis": basis,
    }


def gate_reason(state):
    """Why this request must not be sent, or None to let it through.

    The fitted estimate is the only ground, and it is not a trustworthy one. It
    has been wrong by a factor of two in this repo's own measurements, and
    refusing on a bad one idles every agent on the machine until the window
    turns over, which is the more expensive mistake because nobody notices it.
    So it blocks only when a measured slope stands behind it (two or more
    readings) and the renewal it would wait for is a time the log actually knows.
    """
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


def report_sleep(events, state):
    """Print seconds for a launcher to sleep; the reason goes to stderr.

    Same test as the gate, so a launcher and a running session never disagree
    about whether the account is serving.
    """
    reason = gate_reason(state)
    if reason is None:
        print(0)
        return
    why, renews = reason
    until = wake_at(renews)
    print(max(0, round((until - now).total_seconds())))
    append_event(
        {"kind": "sleep", "untilT": stamp_seconds(until), "reason": f"{why}; waiting before launch"}
    )
    print(f"credit is out: {why}; waiting until {stamp(until)}", file=sys.stderr)


def run_gate(events, state):
    """Refuse a request outright when credit is gone, else describe the window.

    Exit 2 is what makes this autonomous: the harness drops the prompt before a
    request is sent, so an exhausted window costs nothing at all. Everything
    cheaper than this — a warning in context, a rule the model is asked to
    follow — still spends the request that discovers the window is empty.
    """
    reason = gate_reason(state)
    if reason:
        why, until = reason
        if not newest_sleep_covers(events, until):
            append_event({"kind": "sleep", "untilT": stamp_seconds(wake_at(until)),
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
    if not declared:
        return False
    when = parse_time(declared.get("untilT"))
    return bool(when and when >= until - timedelta(minutes=5))


def main():
    events = read_events()
    state = window_state(events)
    if ARGS.sleep_seconds:
        report_sleep(events, state)
        return
    if ARGS.gate:
        run_gate(events, state)
        return

    out = []

    if state["unlogged"]:
        log_boundary(state["window_start"], state["source"])
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
            f"already ({basis}); the next session start records the new one"
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
