"""Score the blind judge-validation items with the pre-registered judge and compare with any label file. Lead-owned.

  python -m ragbench.judge_items --base-url http://127.0.0.1:8080 --out data/judge_items_scored.jsonl
  python -m ragbench.judge_items --compare data/judge_items_scored.jsonl data/judge_validation_agent.jsonl
"""
import argparse
import json
from pathlib import Path

from ragbench.judge import LENIENT, STRICT, Judge
from ragbench.llm import LLM


def score(src, base_url, out, prompt=LENIENT):
    judge = Judge(LLM(base_url), prompt)
    with open(out, "w") as handle:
        for line in open(src):
            item = json.loads(line)
            before = judge.unparseable
            verdict = judge.supported(item["question"], item["answer"], item["passages"])
            handle.write(json.dumps({"id": item["id"], "category": item["category"],
                                     "judge": None if judge.unparseable > before else verdict}) + "\n")
    print(f"scored {out} unparseable={judge.unparseable}")


def agreement(path_a, path_b, key_a="judge", key_b="label"):
    """Cohen's kappa between two label sources over the ids both cover (None verdicts dropped)."""
    a = {r["id"]: r for r in map(json.loads, open(path_a))}
    b = {r["id"]: r for r in map(json.loads, open(path_b))}
    pairs = [(a[i][key_a], b[i][key_b], a[i].get("category")) for i in a if i in b
             and isinstance(a[i].get(key_a), bool) and isinstance(b[i].get(key_b), bool)]
    n = len(pairs)
    if not n:
        return dict(n=0)
    agree = sum(x == y for x, y, _ in pairs) / n
    pa, pb = sum(x for x, _, _ in pairs) / n, sum(y for _, y, _ in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    kappa = (agree - expected) / (1 - expected) if expected != 1 else float("nan")
    disagree = sorted(i for i in a if i in b and isinstance(a[i].get(key_a), bool)
                      and isinstance(b[i].get(key_b), bool) and a[i][key_a] != b[i][key_b])
    return dict(n=n, agreement=agree, kappa=kappa, rate_a=pa, rate_b=pb, disagree_ids=disagree)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/judge_to_label.jsonl")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--out", default="data/judge_items_scored.jsonl")
    ap.add_argument("--strict", action="store_true", help="judge prompt v2 (STRICT)")
    ap.add_argument("--compare", nargs=2, metavar=("JUDGE_FILE", "LABEL_FILE"))
    a = ap.parse_args()
    if a.compare:
        print(json.dumps(agreement(*a.compare), indent=1))
    else:
        score(a.src, a.base_url, a.out, STRICT if a.strict else LENIENT)


if __name__ == "__main__":
    main()
