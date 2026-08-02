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

The window length is an assumption until a report confirms it — override with
CLAUDE_USAGE_WINDOW_MINUTES.

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
    parser.add_argument("--session", help="session id to tag anything this run appends to the log")
    return parser.parse_args()


ARGS = parse_args()
# stdin is the hook payload only when the harness invoked us; a launcher passes --session.
SESSION_ID = ARGS.session or (None if ARGS.sleep_seconds else hook_session_id())


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


def find_window_start(events):
    """Earliest first-request since the last window ended, or None if none is open."""
    boundary = None
    limit_hit = newest(events, "limit-hit")
    renewed = newest(events, "renewed")
    for candidate in (limit_hit and parse_time(limit_hit.get("resetAt")), renewed and renewed["_t"]):
        if candidate and (boundary is None or candidate > boundary):
            boundary = candidate

    starts = [
        e["_t"] for e in events
        if e.get("kind") == "first-request" and (boundary is None or e["_t"] >= boundary)
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
    limit_hit = newest(events, "limit-hit")
    if limit_hit:
        reset_at = parse_time(limit_hit.get("resetAt"))
        if reset_at and reset_at > now:
            waits.append((reset_at, f"limit-hit at {stamp(limit_hit['_t'])} puts renewal at {stamp(reset_at)}"))

    declared = newest(events, "sleep")
    if declared:
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


def main():
    events = read_events()
    if ARGS.sleep_seconds:
        report_sleep(events)
        return

    out = []

    limit_hit = newest(events, "limit-hit")
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

    window_start = find_window_start(events)
    if window_start is None:
        log_first_request()
        window_start = now
        opened = " (this session opened it)"
    else:
        opened = ""

    requests, sessions = scan_transcripts(window_start)
    totals = {name: 0 for name, _ in TOKEN_FIELDS}
    by_model = {}
    for _, counts, model in requests.values():
        for name in totals:
            totals[name] += counts[name]
        by_model[model] = by_model.get(model, 0) + sum(counts.values())
    spent = sum(totals.values())

    report = None
    for event in reversed(events):
        if event.get("kind") == "usage-report" and event["_t"] >= window_start:
            report = event
            break

    renews = None
    if report and isinstance(report.get("renewsInMin"), (int, float)):
        renews = report["_t"] + timedelta(minutes=report["renewsInMin"])
        basis = f"reported at {stamp(report['_t'])}"
    else:
        renews = window_start + WINDOW
        basis = f"assumes a {duration(WINDOW)} window — unconfirmed"

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
    if report:
        observed = renews - window_start
        if abs(observed - WINDOW) > timedelta(minutes=5):
            out.append(
                f"  note     that makes this window {duration(observed)}, not the assumed "
                f"{duration(WINDOW)} — correct usage/notes.md"
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

    reports = [e for e in events if e.get("kind") == "usage-report" and e["_t"] >= window_start
               and isinstance(e.get("pct"), (int, float))]
    last = reports[-1] if reports else None
    per_pct = 0
    if len(reports) >= 2 and requests:
        first = reports[0]
        delta_pct = last["pct"] - first["pct"]
        delta_tokens = tokens_through(requests, last["_t"]) - tokens_through(requests, first["_t"])
        if delta_pct > 0 and delta_tokens > 0:
            per_pct = delta_tokens / delta_pct
    if not per_pct and last and requests:
        measured = tokens_through(requests, last["_t"])
        if last["pct"] > 0 and measured > 0:
            per_pct = measured / last["pct"]

    if per_pct:
        estimate = last["pct"] + (spent - tokens_through(requests, last["_t"])) / per_pct
        line = (
            f"  estimate ~{min(estimate, 100):.0f}% used, from {per_pct:,.0f} tokens/% calibrated "
            f"on the {last['pct']}% reported at {stamp(last['_t'])}"
        )
        elapsed = (now - window_start).total_seconds() / 60
        if estimate >= 100:
            line += "; that calibration says the window is already spent — expect a refusal, and "
            line += "ask for a fresh reading before trusting it"
        elif elapsed > 0 and spent > 0:
            empty = now + timedelta(minutes=(100 - estimate) * per_pct / (spent / elapsed))
            verdict = "before renewal — pace or stop early" if empty < renews else "after renewal"
            line += f"; at the current rate credit runs out {stamp(empty)} ({verdict})"
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
