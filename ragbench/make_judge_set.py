"""Build the blind labelling set for judge validation (PREREG: 100 operator labels, stratified). Lead-owned.

  python -m ragbench.make_judge_set --configs configs/s17_react_c0.yaml configs/s17_plan_c0.yaml --n 100 --out data/judge_to_label.jsonl

Only answered rows (not abstained, not parse_failed) with at least one cited AND retrieved passage qualify, because only those reach the judge.
The judge verdict is never written here, so labelling stays blind. Passage text is exactly what the judge sees (overlay applied, OBS_CHARS).
"""
import argparse, json, random
from pathlib import Path

import yaml

from ragbench.data import build_corpus, load_items, read_splits
from ragbench.run import build_cases, case_key, read_rows, row_key
from ragbench.schema import OBS_CHARS, AttackCase

QUOTA = {"clean": 30, "unsupported_claim": 30, "counterfactual": 20, "injection": 10, "citation_hallucination": 10}


def candidates(config_path, items, corpus):
    config = yaml.safe_load(Path(config_path).read_text())
    by_qid = {i.qid: i for i in items}
    pool = [by_qid[q] for q in read_splits()[config.get("split", "eval")]]
    base = {p.id: p for p in corpus}
    out_dir = Path(config.get("out_dir", f"results/{config['name']}"))
    for seed in config.get("seeds", [0]):
        lookup = {case_key(c): c for c in build_cases(pool, config, seed, corpus=corpus)}
        for row in read_rows(out_dir / f"seed{seed}.jsonl"):
            if row["abstained"] or row.get("parse_failed"):
                continue
            case = lookup.get(row_key(row)[1:])
            if case is None:
                continue
            passages = dict(base)
            if isinstance(case, AttackCase):
                passages.update({p.id: p for p in case.corpus_add})
                for pid in case.corpus_remove:
                    passages.pop(pid, None)
            texts = [passages[pid].text[:OBS_CHARS] for pid in dict.fromkeys(row["citations"]) if pid in passages and pid in row["retrieved_ids"]]
            if texts:
                yield {"id": f"{config['name']}:{seed}:{row['category']}:{row['qid']}", "category": row["category"], "qid": row["qid"],
                       "question": case.question, "answer": row["answer"], "passages": texts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out", default="data/judge_to_label.jsonl")
    a = ap.parse_args()
    items = load_items()
    corpus = build_corpus(items)
    pool = [c for cfg in a.configs for c in candidates(cfg, items, corpus)]
    rng = random.Random(a.seed)
    rng.shuffle(pool)
    picked, ids = [], set()
    for cat, quota in QUOTA.items():  # stratified quotas first, then fill from whatever remains
        for c in [c for c in pool if c["category"] == cat][: round(quota * a.n / 100)]:
            picked.append(c); ids.add(c["id"])
    picked += [c for c in pool if c["id"] not in ids][: max(0, a.n - len(picked))]
    rng.shuffle(picked)
    Path(a.out).write_text("".join(json.dumps(c) + "\n" for c in picked[: a.n]))
    from collections import Counter
    print(f"candidates={len(pool)} written={len(picked[:a.n])} by_category={dict(Counter(c['category'] for c in picked[:a.n]))}")


if __name__ == "__main__":
    main()
