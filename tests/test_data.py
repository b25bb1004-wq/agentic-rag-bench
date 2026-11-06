import random

import pandas as pd
import pytest

from ragbench.data import build_corpus, load_items, make_splits, read_splits, write_splits


@pytest.fixture
def items(tmp_path):
    rows = [
        {
            "id": f"q{i}", "question": f"Question {i}?", "answer": "yes",
            "type": "comparison", "level": "easy",
            "supporting_facts": {"title": [f"Title {i}", "Shared", f"Title {i}"],
                                 "sent_id": [0, 0, 1]},
            "context": {"title": ["Shared", f"Title {i}"],
                        "sentences": [[f"Shared version {i}."], ["First.", "Second."]]},
        }
        for i in range(6)
    ]
    path = tmp_path / "fixture.parquet"
    pd.DataFrame(rows).to_parquet(path)
    return load_items(path)


def test_load_and_corpus(items):
    assert len(items) == 6
    assert items[0].qid == "q0"
    assert items[0].question == "Question 0?"
    assert items[0].answer == "yes"
    assert items[0].qtype == "comparison"
    assert items[0].gold_ids == ["p:Title 0", "p:Shared"]
    assert [p.id for p in items[0].passages] == ["p:Shared", "p:Title 0"]
    assert items[0].passages[1].text == "First. Second."
    corpus = build_corpus(items)
    assert len(corpus) == 7
    assert corpus[0].text == "Shared version 0."
    assert len({p.id for p in corpus}) == len(corpus)
    assert build_corpus([]) == []


def test_splits(items, tmp_path):
    state = random.getstate()
    splits = make_splits(items, seed=13, n_train=3, n_eval=2, n_dev=1)
    assert random.getstate() == state
    assert splits == make_splits(items, seed=13, n_train=3, n_eval=2, n_dev=1)
    assert splits != make_splits(items, seed=14, n_train=3, n_eval=2, n_dev=1)
    train, evaluation, dev = (set(splits[key]) for key in ("train", "eval", "dev"))
    assert [len(train), len(evaluation), len(dev)] == [3, 2, 1]
    assert not (train & evaluation or train & dev or evaluation & dev)
    assert train | evaluation | dev == {item.qid for item in items}
    # Shared is the only overlapping title among three unique eval gold titles.
    assert splits["title_overlap"] == pytest.approx(1 / 3)
    path = tmp_path / "nested" / "splits.json"
    write_splits(path, splits=splits)
    assert read_splits(path) == splits


def test_split_edge_cases(items):
    with pytest.raises(ValueError, match="Not enough"):
        make_splits(items)
    with pytest.raises(ValueError, match="nonnegative"):
        make_splits(items, n_train=-1)
    with pytest.raises(ValueError, match="unique"):
        make_splits(items + items, n_train=1, n_eval=1, n_dev=1)
    assert make_splits([], n_train=0, n_eval=0, n_dev=0) == {
        "train": [], "eval": [], "dev": [], "title_overlap": 0.0,
    }
