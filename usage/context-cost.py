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

With no argument, uses the newest usage-report in events.jsonl to place the
window: renewal minus five hours.
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
            if e.get("type") == "assistant" and isinstance(usage, dict):
                events.append(("req", None))
                if first_usage is None:
                    first_usage = usage
                cache_read += usage.get("cache_read_input_tokens", 0)
            elif e.get("type") in ("assistant", "user"):
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


main()
