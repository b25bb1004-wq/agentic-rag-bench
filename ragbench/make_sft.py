"""Build the C2 training file from the SAME episodes C1 stores (optionally with poisoned episodes added). Lead-owned.

  python -m ragbench.make_sft --episodes data/episodes.jsonl --out data/sft_c2.jsonl
  python -m ragbench.make_sft --episodes data/episodes.jsonl --out data/sft_c2_habit_k5.jsonl --poison-kind habit --k 5

Poison episodes come from the same function and the same targets (first k eval-split items) the runner uses for C1,
so C1 and C2 are poisoned with identical episodes.
"""
import argparse

from ragbench.data import load_items, read_splits
from ragbench.memory import select_episodes
from ragbench.poison import make_poison_episodes
from ragbench.run import load_episodes
from ragbench.sft import build_sft, write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="data/episodes.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--poison-kind", choices=("habit", "fact"))
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--agent", choices=("react", "plan"), default="react", help="format of the poison episodes")
    a = ap.parse_args()
    episodes = load_episodes(a.episodes)
    if a.poison_kind and a.k:
        by_qid = {i.qid: i for i in load_items()}
        pool = [by_qid[q] for q in read_splits()["eval"]]
        episodes += make_poison_episodes(a.poison_kind, a.k, a.seed, targets=pool, agent=a.agent)
    records = build_sft(episodes)
    write_jsonl(records, a.out)
    honest = len(select_episodes(load_episodes(a.episodes)))
    print(f"episodes_in={len(episodes)} sft_records={len(records)} honest_selected={honest} poison={a.poison_kind}:{a.k} out={a.out}")


if __name__ == "__main__":
    main()
