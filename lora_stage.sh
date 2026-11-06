#!/bin/zsh
# One C2 variant end to end: SFT file -> LoRA train -> merge -> GGUF q8_0 -> serve -> run. Lead-owned.
#   ./lora_stage.sh c2                          # honest episodes only, full eval config s17_react_c2
#   ./lora_stage.sh c2_poison_habit_k5 habit 5  # poisoned variant, clean-only config
# Needs the base server STOPPED while training (Mac GPU limit); this script stops it and starts the variant server.
set -u
cd "$(dirname "$0")" || exit 1
NAME=$1; KIND=${2:-}; K=${3:-0}
# single-instance lock: two trainers at once exhaust the Mac GPU (learned 2026-11-03)
LOCK=logs/lora.lock; mkdir -p logs
if ! mkdir $LOCK 2>/dev/null; then echo "another lora_stage is running" >&2; exit 1; fi
trap "rmdir $LOCK" EXIT
PY=~/.venvs/ragbench/bin/python
BASE=~/Models/qwen3-1.7b/hf
OUT=models/$NAME; mkdir -p $OUT logs
log() { echo "$(date +%H:%M:%S) $1" >> logs/runs.log; }
log "lora start $NAME"
if [ -n "$KIND" ]; then
  $PY -W ignore -m ragbench.make_sft --poison-kind $KIND --k $K --out $OUT/sft.jsonl > logs/sft_$NAME.log 2>&1 || { log "lora FAIL sft $NAME"; exit 1; }
else
  $PY -W ignore -m ragbench.make_sft --out $OUT/sft.jsonl > logs/sft_$NAME.log 2>&1 || { log "lora FAIL sft $NAME"; exit 1; }
fi
pkill -f "[l]lama-server"; sleep 4
RAGBENCH_TOKENIZER=$BASE $PY -W ignore -m ragbench.train_lora --base $BASE --data $OUT/sft.jsonl --out $OUT/adapter --epochs 2 --lr 2e-4 --rank 16 --alpha 32 --max_len 2048 --bs 1 --grad_accum 8 --seed 0 > logs/train_$NAME.log 2>&1 || { log "lora FAIL train $NAME"; exit 1; }
log "lora trained $NAME"
$PY -W ignore -c "from ragbench.merge_export import merge; merge('$BASE', '$OUT/adapter', '$OUT/merged_hf')" > logs/merge_$NAME.log 2>&1 || { log "lora FAIL merge $NAME"; exit 1; }
( cd ~/Projects/llama.cpp && PYTHONPATH=gguf-py $PY convert_hf_to_gguf.py ~/Projects/agentic-rag-bench/$OUT/merged_hf --outtype q8_0 --outfile ~/Projects/agentic-rag-bench/$OUT/$NAME.gguf > ~/Projects/agentic-rag-bench/logs/convert_$NAME.log 2>&1 ) || { log "lora FAIL convert $NAME"; exit 1; }
rm -rf $OUT/merged_hf   # own regenerable intermediate (adapter and GGUF are kept)
log "lora converted $NAME"
( nohup llama-server -m $OUT/$NAME.gguf --port 8080 -ngl 99 -c 24576 -np 4 --jinja --cache-ram 256 > logs/llama_$NAME.log 2>&1 & )
for i in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok && break; sleep 4; done
CFG=configs/s17_react_$NAME.yaml
[ -f $CFG ] || { log "lora FAIL no config $CFG"; exit 1; }
log "run start $NAME"
$PY -W ignore -m ragbench.run --config $CFG > logs/run_$NAME.log 2>&1
log "run end $NAME rc=$?"
