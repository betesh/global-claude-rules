#!/bin/sh
# Nudges a checkpoint at the end of a turn when context is large and the
# session never went idle enough to trip usage-gate.sh's own trigger.
# install-hooks.sh registers it:
#
#   Stop  ./checkpoint-stop.sh   JSON stdout can block the turn from ending
#
# Any error exits 0: a bug here must never trap a turn from ending.
#
# Locates its own repo, so the clone can live anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")

command -v python3 >/dev/null 2>&1 || exit 0

REPO_DIR="$REPO_DIR" python3 "$SCRIPT_DIR/checkpoint_stop.py"
exit 0
