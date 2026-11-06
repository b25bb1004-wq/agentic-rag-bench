#!/bin/zsh
# Upload the repo as the private dataset <your-user>/ragbench-src and push one plan as a private GPU kernel.
#   KAGGLE_API_TOKEN=... kaggle/push.sh data            # create or version the dataset
#   KAGGLE_API_TOKEN=... kaggle/push.sh smoke 1.6       # push and run plan "smoke" with a 1.6 h budget
set -eu
cd "$(dirname "$0")/.."
K=~/.venvs/kaggle/bin/kaggle
STAGE=${RB_STAGE:-${CLAUDE_JOB_DIR:-/tmp}/tmp/kaggle_stage}
USER_=${KAGGLE_USER:?set KAGGLE_USER to your Kaggle username}  # your Kaggle username
if [ "$1" = data ]; then
  rm -rf $STAGE/ds && mkdir -p $STAGE/ds
  git diff --quiet HEAD -- ragbench configs kaggle || { echo "commit ragbench/configs/kaggle first" >&2; exit 1; }
  git rev-parse --short HEAD > kaggle/VERSION
  BEFORE=$($K datasets list --mine --csv 2>/dev/null | grep "^$USER_/ragbench-src," | cut -d, -f4)
  # code, configs and the three data files; never results, models, logs or secrets. COPYFILE_DISABLE drops macOS ._ files
  COPYFILE_DISABLE=1 tar -czf $STAGE/ds/repo.tar.gz ragbench configs kaggle data/splits.json data/hotpot_val.parquet data/episodes.jsonl data/judge_to_label.jsonl data/operator_review_ids.txt data/judge_validation.jsonl
  print -r -- "{\"title\": \"ragbench-src\", \"id\": \"$USER_/ragbench-src\", \"licenses\": [{\"name\": \"other\"}]}" > $STAGE/ds/dataset-metadata.json
  if $K datasets status $USER_/ragbench-src >/dev/null 2>&1; then
    $K datasets version -p $STAGE/ds -m "repo $(git rev-parse --short HEAD)"
  else
    $K datasets create -p $STAGE/ds
  fi
  # a kernel pushed before the new version is processed mounts the old one (happened 2026-11-04)
  for i in $(seq 1 60); do
    NOW=$($K datasets list --mine --csv 2>/dev/null | grep "^$USER_/ragbench-src," | cut -d, -f4)
    [ -n "$NOW" ] && [ "$NOW" != "$BEFORE" ] && [ "$($K datasets status $USER_/ragbench-src 2>/dev/null | tail -1)" = ready ] && { echo "dataset $(cat kaggle/VERSION) live at $NOW"; exit 0; }
    sleep 10
  done
  echo "dataset version not live after 10 min" >&2; exit 1
fi
PLAN=$1; HOURS=$2; SLUG=${RB_SLUG:-ragbench-$PLAN}  # RB_SLUG: continuation sessions of a plan
rm -rf $STAGE/$PLAN && mkdir -p $STAGE/$PLAN
sed -e "s/__PLAN__/$PLAN/" -e "s/__HOURS__/$HOURS/" kaggle/bootstrap.py > $STAGE/$PLAN/run.py
SOURCES=${RB_KERNEL_SOURCES:-}
print -r -- "{\"id\": \"$USER_/$SLUG\", \"title\": \"$SLUG\", \"code_file\": \"run.py\", \"language\": \"python\",
 \"kernel_type\": \"script\", \"is_private\": true, \"enable_gpu\": true, \"enable_internet\": true,
 \"dataset_sources\": [\"$USER_/ragbench-src\"], \"kernel_sources\": [${SOURCES}], \"competition_sources\": []}" > $STAGE/$PLAN/kernel-metadata.json
$K kernels push -p $STAGE/$PLAN --accelerator NvidiaTeslaT4
