#!/usr/bin/env bash
# Serve one Block 2 backbone on :8000 and block until it answers, or fail loudly.
#
# One backbone at a time: a single RTX 5090 (32 GiB) holds exactly one of these
# at bf16. Weights are also evicted around the run order (see RUNPLAN "Disk
# budget"), so this script only serves -- it never fetches or deletes.
#
#   usage: serve.sh <hf-repo> <tool-call-parser> [extra vllm args...]
#
# VLLM_USE_FLASHINFER_SAMPLER=0 is not optional on this host: FlashInfer's JIT
# needs CUDA >= 12.9 to recognise the 5090's sm120 and the system nvcc is 12.8,
# so the sampler raises "requires GPUs with sm75 or higher" mid-startup.
set -uo pipefail

REPO="${1:?usage: serve.sh <hf-repo> <tool-call-parser> [extra args]}"
PARSER="${2:?usage: serve.sh <hf-repo> <tool-call-parser> [extra args]}"
shift 2

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SLUG="$(echo "$REPO" | tr '/' '_')"
LOG="$ROOT/logs/vllm_${SLUG}.log"
TS="$ROOT/logs/vllm_start.ts"
DEADLINE=1800          # a cold load is ~5.5 min; well past that means stuck

set -a; . "$ROOT/.env"; set +a

tmux kill-session -t vllm 2>/dev/null
# the GPU is not free the instant tmux returns; wait for the old process to go
for _ in $(seq 1 60); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
    [ "$used" -lt 2000 ] && break
    sleep 2
done

: > "$LOG"
tmux new-session -d -s vllm \
  "source /venv/main/bin/activate && \
   export HF_TOKEN='${HF_TOKEN:-}' VLLM_USE_FLASHINFER_SAMPLER=0 && \
   date +%s.%N > '$TS' && \
   vllm serve '$REPO' --served-model-name '$REPO' \
     --max-model-len 16384 --gpu-memory-utilization 0.90 \
     --tool-call-parser '$PARSER' --enable-auto-tool-choice \
     --port 8000 $* >> '$LOG' 2>&1"

echo "[serve] $REPO  parser=$PARSER  log=$LOG"
start=$(date +%s)
while true; do
    if curl -s -m 2 http://localhost:8000/v1/models 2>/dev/null | grep -q "$REPO"; then
        printf '[serve] READY after %ds\n' "$(( $(date +%s) - start ))"
        exit 0
    fi
    if ! tmux has-session -t vllm 2>/dev/null; then
        echo "[serve] FAILED: vllm exited"
        grep -E "RuntimeError|ValueError|Error:|error:" "$LOG" | tail -8
        exit 1
    fi
    if [ $(( $(date +%s) - start )) -gt $DEADLINE ]; then
        echo "[serve] FAILED: no /v1/models after ${DEADLINE}s"; tail -5 "$LOG"; exit 1
    fi
    sleep 5
done
