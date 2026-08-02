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


def usage_lines(path):
    """(when, usage, request key) for each assistant request in a transcript.

    One request streams as several lines sharing a requestId, each carrying the
    running totals, so the key is what lets a caller keep the last of them and
    count the request once.
    """
    for line in open(path, errors="replace"):
        if '"usage"' not in line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = (e.get("message") or {}).get("usage")
        if e.get("type") != "assistant" or not isinstance(usage, dict):
            continue
        try:
            when = datetime.fromisoformat((e.get("timestamp") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        yield when, usage, e.get("requestId") or e.get("uuid")


def context_size(usage):
    """What a request sent, which is what the session was holding at that moment.

    Output tokens are not context: they are produced by the request, not carried
    into it, and they reach the next request as part of its cached prefix.
    """
    return (usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0))


def carried_per_session(since):
    """What each session spent on history it already held when the window opened.

    Context at the boundary times requests since it: every one of those requests
    re-sent that history, so the product is what clearing at the boundary would
    have saved. A session whose first request came after the boundary brought
    nothing in and scores zero, however large it has since grown — clearing it
    saves only what it just paid for.
    """
    rows, cache_read = [], 0
    for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl"))):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < since:
                continue
        except OSError:
            continue
        at_start, after = 0, {}
        for when, usage, key in usage_lines(path):
            if when <= since:
                at_start = context_size(usage)
            else:
                after[key] = usage
        if not after:
            continue
        cache_read += sum(u.get("cache_read_input_tokens", 0) for u in after.values())
        rows.append((at_start * len(after), at_start, len(after), path))
    return sorted(rows, reverse=True), cache_read


def report_carried(since):
    rows, cache_read = carried_per_session(since)
    print(f"\ncarried in, per session (context at {since:%H:%M}Z × requests since)\n")
    print(f"  {'session':56s} {'at start':>9s} {'req':>5s} {'carried':>13s}  share")
    for carried, at_start, requests, path in rows:
        name = f"{os.path.basename(os.path.dirname(path))}/{os.path.basename(path)[:8]}"
        share = f"{100 * carried / cache_read:5.1f}%" if cache_read else "    -"
        print(f"  {name[-56:]:56s} {at_start:>9,} {requests:>5} {carried:>13,}  {share}")
    total = sum(r[0] for r in rows)
    share = f"{100 * total / cache_read:5.1f}%" if cache_read else "    -"
    print(f"  {'TOTAL':56s} {'':9s} {'':5s} {total:>13,}  {share}")
    print(f"\n  window cache-read {cache_read:,} across {len(rows)} sessions")


def main():
    since = (
        datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
        if len(sys.argv) > 1 else window_start_from_log()
    )
    if not since:
        sys.exit("no open window in events.jsonl; pass a start time explicitly")
    print(f"window from {since:%Y-%m-%dT%H:%MZ}\n")

    tally, carried, cache_read = {}, 0, 0
    for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "projects", "*", "*.jsonl"))):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < since:
                continue
        except OSError:
            continue
        events, first_usage = [], None
        for line in open(path, errors="replace"):
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            stamp = e.get("timestamp")
            if not stamp:
                continue
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if when < since:
                continue
            message = e.get("message") or {}
            usage = message.get("usage")
            # An assistant message is both a request and a set of blocks that stay
            # in context; counting only the first drops every reply and tool call.
            if e.get("type") == "assistant" and isinstance(usage, dict):
                events.append(("req", None))
                if first_usage is None:
                    first_usage = usage
                cache_read += usage.get("cache_read_input_tokens", 0)
            if e.get("type") in ("assistant", "user"):
                for label, n in blocks(message.get("content")):
                    label = "user prompt" if (e["type"] == "user" and label == "text") else label
                    events.append((label, n // 4))
        requests = sum(1 for k, _ in events if k == "req")
        if requests < 5 or not first_usage:
            continue

        # Everything already in context when this session's first in-window
        # request went out, charged to every request that followed it.
        at_open = (first_usage.get("cache_read_input_tokens", 0)
                   + first_usage.get("cache_creation_input_tokens", 0))
        carried += at_open * requests
        print(f"  {os.path.basename(os.path.dirname(path))[:48]:48s} "
              f"{requests:>4} req, carried in {at_open:>9,}")

        seen = 0
        for label, n in events:
            if label == "req":
                seen += 1
            else:
                tally[label] = tally.get(label, 0) + n * (requests - seen)

    total = carried + sum(tally.values())
    print(f"\n{'source':18s} {'tokens':>14s}  share")
    rows = [("carried in", carried)] + sorted(tally.items(), key=lambda kv: -kv[1])
    for label, value in rows:
        if value:
            print(f"{label:18s} {value:>14,}  {100 * value / total:5.1f}%")
    print(f"{'TOTAL':18s} {total:>14,}")
    if cache_read:
        print(f"\nmeasured cache-read this window: {cache_read:,} "
              f"({100 * total / cache_read:.0f}% accounted for)")

    report_carried(since)


main()
