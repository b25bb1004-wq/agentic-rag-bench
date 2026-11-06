#!/bin/zsh
# S4 (PREREG 2026-11-04): C1 poison dose-response on the Mac, k in {2,10,50}; k 1/5/25 already exist. Lead-owned.
set -u
cd "$(dirname "$0")" || exit 1
LOCK=logs/sweep_c1.lock; mkdir -p logs
if ! mkdir $LOCK 2>/dev/null; then echo "sweep_c1 already running" >&2; exit 1; fi
trap "rmdir $LOCK; pkill -f '[l]lama-server.*qwen3-1.7b-base'" EXIT
log() { echo "$(date +%H:%M:%S) $1" >> logs/runs.log; }
pkill -f "[l]lama-server"; sleep 3
( nice -n 10 llama-server -m ~/Models/qwen3-1.7b/gguf/qwen3-1.7b-base-q8_0.gguf --port 8080 -ngl 99 -c 24576 -np 4 --jinja --cache-ram 256 > logs/llama_sweep_c1.log 2>&1 & )
for i in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok && break; sleep 4; done
for k in 2 10 50; do for kind in habit fact; do
  N=s17_react_c1_poison_${kind}_k$k
  log "run start $N"
  nice -n 10 ~/.venvs/ragbench/bin/python -W ignore -m ragbench.run --config configs/$N.yaml > logs/run_$N.log 2>&1
  log "run end $N rc=$?"
done; done
