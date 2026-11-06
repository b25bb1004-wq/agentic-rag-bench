"""Shared dataclasses. Owned by the lead. Workers import, never redefine."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

OBS_CHARS = 600   # characters of a passage the agent sees in an observation; attacks must keep their edit inside this window
CATEGORIES = ("injection", "jailbreak", "citation_hallucination", "unsupported_claim", "counterfactual")


@dataclass(frozen=True)
class Passage:
    id: str      # "p:" + title
    title: str
    text: str


@dataclass
class Item:
    qid: str
    question: str
    answer: str
    gold_ids: list[str]
    qtype: str
    passages: list[Passage]


@dataclass
class Step:
    kind: str          # "plan" | "search" | "answer"
    arg: str
    observation: str = ""


@dataclass
class Trajectory:
    qid: str
    question: str
    answer: str
    citations: list[str]
    steps: list[Step]
    retrieved_ids: list[str]
    raw: str = ""
    n_llm_calls: int = 0
    abstained: bool = False        # explicit "Final: UNKNOWN" (or empty answer in a valid Final line)
    parse_failed: bool = False     # no parseable Final line at all: counted separately, never as robustness

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttackCase:
    case_id: str
    category: str
    qid: str
    question: str
    answer_gold: str | None          # None when the question has no valid answer in the case corpus
    corpus_add: list[Passage] = field(default_factory=list)
    corpus_remove: list[str] = field(default_factory=list)
    system_extra: str = ""           # extra system text (jailbreak policy / canary), else ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
