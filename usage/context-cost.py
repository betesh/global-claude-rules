#!/usr/bin/env python3
"""Where a credit window's cache-read actually went.

    python3 usage/context-cost.py [WINDOW_START_ISO]

Every request re-sends the whole context, so cache-read for a window is roughly
the sum of each request's context size. This attributes that sum to what put the
tokens there, which is the only view that says what to change.

The trap this exists to avoid: attributing blocks by when they were *added*
cannot see anything added before the window started, and silently charges it to
fixed overhead instead. A long-lived session carries its whole history across the
boundary, so that invisible share is usually the largest one — measured at 59% in
one window, against 8% for tool results. Reported here as "carried in".

What a session held when the window opened is two different things, and they are
reported separately because they have different remedies. The **floor** is what
its very first request already cost — system prompt, tool schemas, project
instructions — which every session pays and no amount of clearing removes.
"Carried in" is only what it held *beyond* that floor at the boundary, which is
what clearing before the boundary would have saved.

Everything measured comes from the transcripts. With no argument the newest
usage-report in events.jsonl places the window — renewal minus five hours — but
that log is a scratch record of what agents observed and can be emptied at any
time, so pass the start explicitly and nothing here depends on it.
"""

import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW = timedelta(hours=5)


def window_start_from_log():
    path = os.path.join(REPO_DIR, "usage", "events.jsonl")
    newest = None
    try:
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") == "usage-report" and isinstance(e.get("renewsInMin"), (int, float)):
                    t = datetime.fromisoformat(e["t"].replace("Z", "+00:00"))
                    renews = t + timedelta(minutes=e["renewsInMin"])
                    if renews > datetime.now(timezone.utc) and (newest is None or renews > newest):
                        newest = renews
    except OSError:
        pass
    return newest - WINDOW if newest else None


def blocks(content):
    """(label, characters) for each block that occupies context."""
    if isinstance(content, str):
        return [("text", len(content))]
    out = []
    for b in content if isinstance(content, list) else []:
        if not isinstance(b, dict):
            continue
        kind = b.get("type")
        if kind == "text":
            out.append(("assistant text", len(b.get("text") or "")))
        elif kind == "thinking":
            out.append(("thinking", len(b.get("thinking") or "")))
        elif kind == "tool_use":
            out.append(("tool call", len(json.dumps(b.get("input") or {}))))
        elif kind == "tool_result":
            c = b.get("content")
            out.append(("tool result", len(c) if isinstance(c, str) else len(json.dumps(c or ""))))
    return out


def context_size(usage):
    """What a request sent, which is what the session was holding at that moment.

    Output tokens are not context: they are produced by the request, not carried
    into it, and they reach the next request as part of its cached prefix.
    """
    return (usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0))


def transcripts(since):
    for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl"))):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) >= since:
                yield path
        except OSError:
            continue


def prefix(usage):
    """The cached prefix a request sent: everything it did not have to compose."""
    return (usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0))


def walk(path, since):
    """One pass over a transcript: what it held at `since`, and what came after.

    Returns the session's floor (its very first request's prefix, whenever that
    was), the context size at the boundary, the request ids in order, the last
    usage line seen for each — one request streams as several lines sharing a
    requestId, each carrying the running totals, so counting lines counts the
    same request several times over — and the timeline of blocks and requests
    that followed.
    """
    floor, at_start, order, usages, timeline = 0, 0, [], {}, []
    for line in open(path, errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            when = datetime.fromisoformat((e.get("timestamp") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        message = e.get("message") or {}
        usage = message.get("usage")
        # A synthetic assistant message carries an all-zero usage block and was
        # never sent anywhere. Counting it as a request scores that session's
        # floor as zero, since it is usually the first line in the file.
        is_request = (e.get("type") == "assistant" and isinstance(usage, dict)
                      and context_size(usage) > 0)
        if is_request and not floor:
            floor = prefix(usage)
        if is_request and when <= since:
            at_start = context_size(usage)
        if when < since:
            continue
        if is_request:
            key = e.get("requestId") or e.get("uuid")
            if key not in usages:
                order.append(key)
                # An assistant message is both a request and a set of blocks that
                # stay in context; the marker goes before its own blocks so they
                # are charged to the requests that follow it, not to itself.
                timeline.append(("req", 0))
            usages[key] = usage
        if e.get("type") in ("assistant", "user"):
            for label, n in blocks(message.get("content")):
                label = "user prompt" if (e["type"] == "user" and label == "text") else label
                timeline.append((label, n // 4))
    return floor, at_start, order, usages, timeline


def report_sessions(rows, cache_read, since):
    """What each session spent before doing any work in this window.

    Each figure is a context size times the requests that re-sent it, so it is
    what removing that context at the boundary would have saved. The floor is
    the session's own first request and cannot be removed at all; carried is
    everything it held beyond the floor when the window opened. A session whose
    first request came after the boundary carried nothing in, however large it
    has since grown — clearing it saves only what it just paid for.
    """
    rows = sorted(rows, reverse=True)
    print(f"\nper session, before any work in this window (× requests since {since:%H:%M}Z)\n")
    print(f"  {'session':48s} {'req':>5s} {'floor':>13s} {'carried':>13s}  share")
    for carried, floor_cost, requests, path in rows:
        name = f"{os.path.basename(os.path.dirname(path))}/{os.path.basename(path)[:8]}"
        share = f"{100 * carried / cache_read:5.1f}%" if cache_read else "    -"
        print(f"  {name[-48:]:48s} {requests:>5} {floor_cost:>13,} {carried:>13,}  {share}")
    carried_total, floor_total = sum(r[0] for r in rows), sum(r[1] for r in rows)
    share = f"{100 * carried_total / cache_read:5.1f}%" if cache_read else "    -"
    print(f"  {'TOTAL':48s} {'':5s} {floor_total:>13,} {carried_total:>13,}  {share}")
    print(f"\n  window cache-read {cache_read:,} across {len(rows)} sessions")


def main():
    since = (
        datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
        if len(sys.argv) > 1 else window_start_from_log()
    )
    if not since:
        sys.exit("no open window in events.jsonl; pass a start time explicitly")
    print(f"window from {since:%Y-%m-%dT%H:%MZ}\n")

    tally, carried, floor_cost, cache_read, rows = {}, 0, 0, 0, []
    for path in transcripts(since):
        floor, _, order, usages, timeline = walk(path, since)
        requests = len(order)
        if not requests:
            continue
        cache_read += sum(u.get("cache_read_input_tokens", 0) for u in usages.values())

        # Everything already in context when this session's first in-window
        # request went out, charged to every request that followed it. The part
        # of it the session was born with is the floor; only the rest is history
        # it chose to keep, and only that part answers to clearing.
        at_open = prefix(usages[order[0]])
        session_floor = min(floor, at_open)
        rows.append(((at_open - session_floor) * requests,
                     session_floor * requests, requests, path))
        if requests < 5:
            continue
        carried += (at_open - session_floor) * requests
        floor_cost += session_floor * requests
        print(f"  {os.path.basename(os.path.dirname(path))[:48]:48s} "
              f"{requests:>4} req, floor {session_floor:>8,}, carried in {at_open - session_floor:>9,}")

        seen = 0
        for label, n in timeline:
            if label == "req":
                seen += 1
            else:
                tally[label] = tally.get(label, 0) + n * (requests - seen)

    total = carried + floor_cost + sum(tally.values())
    print(f"\n{'source':18s} {'tokens':>14s}  share")
    fixed = [("carried in", carried), ("floor", floor_cost)]
    for label, value in fixed + sorted(tally.items(), key=lambda kv: -kv[1]):
        if value:
            print(f"{label:18s} {value:>14,}  {100 * value / total:5.1f}%")
    print(f"{'TOTAL':18s} {total:>14,}")
    if cache_read:
        print(f"\nmeasured cache-read this window: {cache_read:,} "
              f"({100 * total / cache_read:.0f}% accounted for)")

    report_sessions(rows, cache_read, since)


main()
