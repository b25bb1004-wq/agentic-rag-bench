"""Load HotpotQA paragraphs and create reproducible question splits."""
from __future__ import annotations

import json
from pathlib import Path
import random

import pandas as pd

from ragbench.schema import Item, Passage


def load_items(path="data/hotpot_val.parquet") -> list[Item]:
    items = []
    for row in pd.read_parquet(path).to_dict(orient="records"):
        context = row["context"]
        passages = [
            Passage("p:" + title, title, " ".join(sentences))
            for title, sentences in zip(context["title"], context["sentences"])
        ]
        gold_ids = list(dict.fromkeys("p:" + t for t in row["supporting_facts"]["title"]))
        items.append(Item(row["id"], row["question"], row["answer"],
                          gold_ids, row["type"], passages))
    return items


def build_corpus(items: list[Item]) -> list[Passage]:
    corpus = {}
    for item in items:
        for passage in item.passages:
            corpus.setdefault(passage.id, passage)
    return list(corpus.values())


def make_splits(items, seed=13, n_train=2000, n_eval=500, n_dev=200) -> dict:
    """Overlap counts unique eval gold titles against all train paragraphs."""
    sizes = (n_train, n_eval, n_dev)
    if any(n < 0 for n in sizes):
        raise ValueError("Split sizes must be nonnegative")
    if len({item.qid for item in items}) != len(items):
        raise ValueError("Question ids must be unique")
    if sum(sizes) > len(items):
        raise ValueError("Not enough items for the requested split sizes")
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    train = shuffled[:n_train]
    evaluation = shuffled[n_train:n_train + n_eval]
    dev = shuffled[n_train + n_eval:sum(sizes)]
    train_titles = {p.id for item in train for p in item.passages}
    eval_gold = {pid for item in evaluation for pid in item.gold_ids}
    return {
        "train": [item.qid for item in train],
        "eval": [item.qid for item in evaluation],
        "dev": [item.qid for item in dev],
        "title_overlap": len(eval_gold & train_titles) / len(eval_gold) if eval_gold else 0.0,
    }


def write_splits(path="data/splits.json", splits=None) -> None:
    """Persist supplied splits, or build default splits from the default data."""
    if splits is None:
        splits = make_splits(load_items())
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(splits, indent=2) + "\n", encoding="utf-8")


def read_splits(path="data/splits.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    splits = make_splits(load_items())
    write_splits(splits=splits)
    print(" ".join(f"{key}={len(splits[key])}" for key in ("train", "eval", "dev")))
    print(f"title_overlap={splits['title_overlap']:.6f}")
