import pytest

from ragbench.retriever import HybridRetriever, Overlay
from ragbench.schema import Passage


@pytest.fixture
def retriever():
    return HybridRetriever([
        Passage("p:Zephyr", "Zephyr", "A special wind."),
        Passage("p:Ocean", "Ocean", "Deep blue water."),
        Passage("p:Mountain", "Mountain", "Tall rocky peak."),
        Passage("p:Forest", "Forest", "Green trees grow."),
    ])


def test_title_and_determinism(retriever):
    result = retriever.search("ZEPHYR!")
    assert result[0][0].id == "p:Zephyr"
    assert result[0][1] > 0
    assert retriever.search("ZEPHYR!") == result
    assert [p.id for p, _ in retriever.search("absent")] == [
        "p:Forest", "p:Mountain", "p:Ocean", "p:Zephyr",
    ]
    assert len(retriever.search("wind", k=2)) == 2
    assert retriever.search("wind", k=0) == []


def test_overlays_preserve_base(retriever):
    before = retriever.search("Zephyr", k=20)
    removed = retriever.search("Zephyr", overlay=Overlay(remove={"p:Zephyr"}))
    assert all(p.id != "p:Zephyr" for p, _ in removed)
    addition = Passage("p:Quasar", "Quasar", "Bright distant object.")
    overlay = Overlay(add=[addition])
    added = retriever.search("quasar", overlay=overlay)
    assert added[0][0] == addition
    assert added[0][1] > 0
    assert retriever.search("quasar", overlay=overlay) == added
    replacement = Passage("p:Zephyr", "Zephyr", "Changed content about wind.")
    replaced = retriever.search("Zephyr", overlay=Overlay(add=[replacement]))
    assert replaced[0][0] == replacement
    assert sum(p.id == replacement.id for p, _ in replaced) == 1
    assert retriever.search("Zephyr", k=20) == before
    assert overlay.add == [addition]
    assert overlay.remove == set()


def test_replacement_scoring_uses_new_text(retriever):
    replacement = Passage("p:Zephyr", "Different", "Changed content.")
    results = dict((p.id, score) for p, score in retriever.search(
        "Zephyr", overlay=Overlay(add=[replacement]),
    ))
    assert results["p:Zephyr"] == 0.0


def test_same_text_overlay_has_same_bm25_score(retriever):
    before = retriever.search("Zephyr")
    assert retriever.search("Zephyr", overlay=Overlay(add=[before[0][0]])) == before


def test_empty_and_overlay_defaults():
    first, second = Overlay(), Overlay()
    first.remove.add("p:x")
    first.add.append(Passage("p:x", "x", "x"))
    assert second == Overlay()
    retriever = HybridRetriever([])
    assert retriever.search("anything") == []
    assert retriever.search("x", overlay=first) == []
    assert retriever.search("x", overlay=Overlay(add=first.add))[0][0] == first.add[0]
    assert HybridRetriever([Passage("p:blank", "", "")]).search("x")[0][1] == 0.0
