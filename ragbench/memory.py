"""Rejection-sampled retrieval memory shared with the SFT condition."""
from dataclasses import dataclass
import re
import random

from rank_bm25 import BM25Okapi
from ragbench.schema import Trajectory


@dataclass
class Episode:
    qid: str
    question: str
    trajectory: Trajectory
    correct: bool


def select_episodes(episodes, max_n=None, seed=0):
    if max_n is not None and max_n < 0:
        raise ValueError("max_n must be nonnegative")
    selected = sorted((ep for ep in episodes if ep.correct), key=lambda ep: ep.qid)
    if max_n is not None:
        selected = random.Random(seed).sample(selected, min(max_n, len(selected)))
    return sorted(selected, key=lambda ep: ep.qid)


def _tokens(text):
    return re.findall(r"\w+", text.lower()) or [""]


class RetrievalMemory:
    def __init__(self, episodes, k=3):
        if k < 0:
            raise ValueError("k must be nonnegative")
        self.k = k
        self.episodes = list(episodes)
        self._rebuild()

    def _rebuild(self):
        self.selected = select_episodes(self.episodes)
        self.index = BM25Okapi([_tokens(ep.question) for ep in self.selected]) if self.selected else None

    def retrieve(self, question):
        return self.retrieve_with_size(question)[0]

    def retrieve_with_size(self, question) -> tuple[str, int]:
        """Return this call's block and token estimate without shared writes."""
        if self.index is None:
            return "", 0
        scores = self.index.get_scores(_tokens(question))
        order = sorted(range(len(self.selected)), key=lambda i: (-scores[i], i))[:self.k]
        lines = []
        for i in order:
            ep = self.selected[i]
            searches = "; ".join(step.arg for step in ep.trajectory.steps if step.kind == "search")
            lines.append(f"Q: {ep.question} | searches: {searches} | Final: {ep.trajectory.answer} | Cite: {','.join(ep.trajectory.citations)}")
        block = "\n".join(lines)
        return block, round(len(block.split()) * 1.3)

    def add(self, episode):
        self.episodes.append(episode)
        self._rebuild()

    def remove(self, qid):
        self.episodes = [ep for ep in self.episodes if ep.qid != qid]
        self._rebuild()
