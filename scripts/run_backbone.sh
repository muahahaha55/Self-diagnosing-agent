#!/usr/bin/env bash
# Run one backbone's three cells, but prove it emits tool calls first.
#
# Stop rule (RUNPLAN, "parser"): a wrong tool-call parser does not raise. The
# server returns prose, the harness records n_tool_calls=0, and 30 trials look
# like zero-step successes. So a single trial runs first and its step count is
# checked; the other 29 only follow if that trial actually called a tool.
set -uo pipefail
REPO="${1:?usage: run_backbone.sh <hf-repo>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source /workspace/venv-harness/bin/activate

echo "=== probe trial: $REPO ==="
python scripts/eta_probe.py --backbone "$REPO" --temperature 0.0 --ids A_clean || exit 1

steps=$(python - "$REPO" <<'PY'
import json, sys
from pathlib import Path
slug = sys.argv[1].replace("/", "_")
rows = json.loads(Path(f"runs/exp_a/raw/{slug}_T0.0_sNone.json").read_text())
r = next(r for r in rows if r["id"] == "A_clean")
print(r["n_tool_calls"])
PY
)
echo "probe trial A_clean: n_tool_calls=$steps"
if [ "$steps" -lt 1 ]; then
    echo "STOP: zero tool calls on the first trial of $REPO -- suspect the parser."
    exit 2
fi

echo "=== full run: $REPO ==="
python scripts/run_exp_a.py --backbone "$REPO"
