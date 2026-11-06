"""BM25 retrieval with immutable per-call overlays and optional dense fusion."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import re

from rank_bm25 import BM25Okapi

from ragbench.schema import Passage


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _passage_tokens(passage: Passage) -> list[str]:
    return _tokens(passage.title) * 2 + _tokens(passage.text)


@dataclass
class Overlay:
    add: list[Passage] = field(default_factory=list)
    remove: set[str] = field(default_factory=set)


class HybridRetriever:
    def __init__(self, passages, dense_model: str | None = None):
        # Deduplicate ids with the same first-occurrence policy as build_corpus.
        unique = {}
        for passage in passages:
            unique.setdefault(passage.id, passage)
        self.passages = tuple(unique.values())
        corpus = [_passage_tokens(p) for p in self.passages]
        self._bm25 = BM25Okapi(corpus) if any(corpus) else None
        self._dense_model = None
        self._embeddings = None
        if dense_model is not None:
            from sentence_transformers import SentenceTransformer

            self._dense_model = SentenceTransformer(dense_model)
            if self.passages:
                self._embeddings = self._dense_model.encode(
                    [self._dense_text(p) for p in self.passages],
                    normalize_embeddings=True, convert_to_numpy=True,
                )

    @staticmethod
    def _dense_text(passage):
        return passage.title + "\n" + passage.text

    def _added_score(self, passage, query):
        tokens = _passage_tokens(passage)
        if not tokens:
            return 0.0
        bm25 = self._bm25
        # With no usable base vocabulary, treat additions as one average document.
        size = len(self.passages)
        avgdl = bm25.avgdl if bm25 else len(tokens)
        k1, b = (bm25.k1, bm25.b) if bm25 else (1.5, 0.75)
        frequencies = Counter(tokens)
        unseen_idf = math.log((size + 0.5) / 0.5)
        score = 0.0
        for token in query:
            frequency = frequencies[token]
            if frequency:
                idf = bm25.idf.get(token, unseen_idf) if bm25 else math.log(3)
                score += idf * (frequency * (k1 + 1) / (
                    frequency + k1 * (1 - b + b * len(tokens) / avgdl)
                ))
        return score

    def search(self, query: str, k: int = 5, overlay: Overlay | None = None):
        if k <= 0:
            return []
        overlay = overlay if overlay is not None else Overlay()
        additions = {p.id: p for p in overlay.add if p.id not in overlay.remove}
        query_tokens = _tokens(query)
        scores = self._bm25.get_scores(query_tokens) if self._bm25 else [0.0] * len(self.passages)
        candidates = {
            p.id: (p, float(score)) for p, score in zip(self.passages, scores)
            if p.id not in overlay.remove and p.id not in additions
        }
        for pid, passage in additions.items():
            candidates[pid] = (passage, self._added_score(passage, query_tokens))
        lexical = sorted(candidates.values(), key=lambda pair: (-pair[1], pair[0].id))
        if not lexical or self._dense_model is None:
            return lexical[:k]

        query_embedding = self._dense_model.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True,
        )[0]
        dense_scores = {}
        if self._embeddings is not None:
            for p, embedding in zip(self.passages, self._embeddings):
                if p.id in candidates and p.id not in additions:
                    dense_scores[p.id] = float(embedding @ query_embedding)
        if additions:
            added_passages = list(additions.values())
            embeddings = self._dense_model.encode(
                [self._dense_text(p) for p in added_passages],
                normalize_embeddings=True, convert_to_numpy=True,
            )
            for p, embedding in zip(added_passages, embeddings):
                dense_scores[p.id] = float(embedding @ query_embedding)
        dense = sorted(dense_scores, key=lambda pid: (-dense_scores[pid], pid))
        fused = {pid: 0.0 for pid in candidates}
        for ranking in ([p.id for p, _ in lexical], dense):
            for rank, pid in enumerate(ranking, start=1):
                fused[pid] += 1.0 / (60 + rank)
        return [(candidates[pid][0], fused[pid]) for pid in
                sorted(fused, key=lambda pid: (-fused[pid], pid))[:k]]
