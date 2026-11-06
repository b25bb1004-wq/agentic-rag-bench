"""Generate training episodes: run the no-memory agent on the TRAIN split and keep every trajectory with its correctness.
Output: JSONL of dataclasses.asdict(Episode), the format run.load_episodes reads. Lead-owned.

  python -m ragbench.make_episodes --agent react --base-url http://127.0.0.1:8080 --n 600 --out data/episodes.jsonl
"""
import argparse, json, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from ragbench.agents.plan import PlanAgent
from ragbench.agents.react import ReActAgent
from ragbench.data import build_corpus, load_items, read_splits
from ragbench.llm import LLM
from ragbench.memory import Episode
from ragbench.metrics import exact_match
from ragbench.retriever import HybridRetriever


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=("react", "plan"), default="react")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--n", type=int, default=600, help="train questions to attempt")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="data/episodes.jsonl")
    ap.add_argument("--resume", action="store_true", help="skip qids already in --out and append")
    a = ap.parse_args()
    items = {i.qid: i for i in load_items()}
    qids = read_splits()["train"][: a.n]
    seen = set()
    if a.resume and Path(a.out).exists():
        for line in open(a.out):
            try:
                seen.add(json.loads(line)["qid"])
            except Exception:
                pass  # a half-written last line from a killed run
        qids = [q for q in qids if q not in seen]
    retriever = HybridRetriever(build_corpus(list(items.values())))  # BM25 only, same corpus as eval runs
    llm, agent = LLM(a.base_url), (ReActAgent() if a.agent == "react" else PlanAgent())

    def one(qid):
        it = items[qid]
        try:
            tr = agent.run(it.question, retriever, llm, seed=a.seed)
        except Exception as e:  # keep going; the count is printed at the end
            return qid, None, repr(e)
        return qid, Episode(qid, it.question, tr, bool(not tr.parse_failed and exact_match(tr.answer, it.answer))), None

    done = errs = ok = 0
    with ThreadPoolExecutor(a.workers) as ex, open(a.out, "a" if a.resume else "w") as f:
        for qid, ep, err in ex.map(one, qids):
            done += 1
            if err:
                errs += 1
                continue
            ok += ep.correct
            f.write(json.dumps(asdict(ep)) + "\n")
            if done % 25 == 0:
                print(f"{done}/{len(qids)} correct={ok} errors={errs}", file=sys.stderr, flush=True)
    print(f"episodes={done - errs} correct={ok} errors={errs} out={a.out}")


if __name__ == "__main__":
    main()
