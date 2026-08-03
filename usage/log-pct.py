#!/usr/bin/env python3
"""Log a usage percentage by hand, without spending an agent request to do it.

    python3 usage/log-pct.py PCT [RENEWS_IN_MIN]

No `session` is attached: that field exists so a line can be traced back to the
transcript that wrote it, and a line appended from a shell has no transcript to
trace to. All a reading needs to be useful is a timestamp, so another one taken
later can compute delta-tokens / delta-time against it.
"""

import argparse
import json
import os
import sys
from datetime import datetime

EVENTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage", "events.jsonl")


def number(raw):
    value = float(raw)
    return int(value) if value.is_integer() else value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pct", type=number, help="percentage of the window used, as shown by the client")
    parser.add_argument("renews_in_min", type=number, nargs="?", help="minutes until renewal, if shown")
    args = parser.parse_args()

    event = {"t": datetime.now().astimezone().isoformat(timespec="seconds"), "kind": "usage-report", "pct": args.pct}
    if args.renews_in_min is not None:
        event["renewsInMin"] = args.renews_in_min

    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event))


if __name__ == "__main__":
    sys.exit(main())
