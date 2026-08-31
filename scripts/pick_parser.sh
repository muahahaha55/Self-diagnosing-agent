#!/usr/bin/env bash
# Serve a backbone under the first tool-call parser that actually produces
# tool calls, trying the candidates in order.
#
# Needed because a mismatched parser fails silently rather than loudly: vLLM
# accepts any registered name, the model emits its own call syntax, the parser
# fails to recognise it, and the API returns the raw text as `content` with
# tool_calls empty. Downstream that is indistinguishable from a model that
# chose not to use tools -- 30 zero-step "successes". The only cheap way to
# tell them apart is to ask one question that has exactly one tool answer.
#
#   usage: pick_parser.sh <hf-repo> <parser> [parser...]
# Leaves the server running under the winning parser and prints it last.
set -uo pipefail
REPO="${1:?usage: pick_parser.sh <hf-repo> <parser> [parser...]}"
shift
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for parser in "$@"; do
    echo "=== trying parser=$parser for $REPO ==="
    if ! bash "$ROOT/scripts/serve.sh" "$REPO" "$parser"; then
        echo "[pick] server would not start under $parser"
        continue
    fi
    if /workspace/venv-harness/bin/python "$ROOT/scripts/smoke_tools.py" "$REPO"; then
        echo "[pick] WINNER parser=$parser"
        echo "$parser" > "$ROOT/logs/parser_$(echo "$REPO" | tr '/' '_').txt"
        exit 0
    fi
    echo "[pick] $parser produced no tool calls"
done
echo "[pick] FAILED: no candidate parser produced tool calls for $REPO"
exit 1
