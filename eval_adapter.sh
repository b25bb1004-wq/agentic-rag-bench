#!/bin/zsh
# Evaluate Kaggle-trained ReAct 1.7B adapters on the Mac with the same merge -> GGUF q8_0 -> serve -> run path
# as lora_stage.sh, so every Mac C2 row comes from one inference stack (PREREG amendment 2026-11-04). Lead-owned.
#   ./eval_adapter.sh <adapters dir> c2_poison_fact_k5 [c2_poison_habit_k1 ...]
# Each name needs <adapters dir>/<name> (peft adapter) and configs/s17_react_<name>.yaml.
set -u
cd "$(dirname "$0")" || exit 1
SRC=$1; shift
LOCK=logs/lora.lock; mkdir -p logs
if ! mkdir $LOCK 2>/dev/null; then echo "another lora/eval stage is running" >&2; exit 1; fi
trap "rmdir $LOCK; pkill -f '[l]lama-server'" EXIT
PY=~/.venvs/ragbench/bin/python
BASE=~/Models/qwen3-1.7b/hf
log() { echo "$(date +%H:%M:%S) $1" >> logs/runs.log; }
for NAME in "$@"; do
  OUT=models/$NAME; CFG=configs/s17_react_$NAME.yaml
  [ -d $SRC/$NAME ] && [ -f $CFG ] || { log "eval FAIL missing adapter or config $NAME"; continue; }
  mkdir -p $OUT && rm -rf $OUT/adapter && cp -R $SRC/$NAME $OUT/adapter
  log "eval start $NAME (Kaggle adapter)"
  $PY -W ignore -c "from ragbench.merge_export import merge; merge('$BASE', '$OUT/adapter', '$OUT/merged_hf')" > logs/merge_$NAME.log 2>&1 || { log "eval FAIL merge $NAME"; continue; }
  ( cd ~/Projects/llama.cpp && PYTHONPATH=gguf-py $PY convert_hf_to_gguf.py ~/Projects/agentic-rag-bench/$OUT/merged_hf --outtype q8_0 --outfile ~/Projects/agentic-rag-bench/$OUT/$NAME.gguf > ~/Projects/agentic-rag-bench/logs/convert_$NAME.log 2>&1 ) || { log "eval FAIL convert $NAME"; continue; }
  rm -rf $OUT/merged_hf   # own regenerable intermediate
  pkill -f "[l]lama-server"; sleep 3
  ( nohup nice -n 10 llama-server -m $OUT/$NAME.gguf --port 8080 -ngl 99 -c 24576 -np 4 --jinja --cache-ram 256 > logs/llama_$NAME.log 2>&1 & )
  for i in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok && break; sleep 4; done
  log "run start $NAME"
  nice -n 10 $PY -W ignore -m ragbench.run --config $CFG > logs/run_$NAME.log 2>&1
  log "run end $NAME rc=$?"
done
