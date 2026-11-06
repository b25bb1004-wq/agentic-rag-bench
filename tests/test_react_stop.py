"""ReActAgent should_stop hook: a stop decision behaves like the search budget."""
import json

from ragbench.agents import ReActAgent
from ragbench.agents.react import SEARCH_BUDGET_DONE
from ragbench.llm import MockLLM
from ragbench.schema import Passage


class FakeRetriever:
    def __init__(self):
        self.calls = []
        self.results = [(Passage("p:A", "A", "First evidence."), 1.0),
                        (Passage("p:B", "B", "Second evidence."), 0.5)]

    def search(self, query, k=5, overlay=None):
        self.calls.append((query, k, overlay))
        return self.results[:k]


def test_stop_after_first_search_refuses_second_like_budget():
    retriever = FakeRetriever()
    reply = "Final: Answer | Cite: p:A"
    llm = MockLLM(["Action: search[first]", "Action: search[second]", reply])
    traj = ReActAgent(should_stop=lambda q, steps, n: n >= 1).run("Question?", retriever, llm)
    assert [call[0] for call in retriever.calls] == ["first"]
    assert {"role": "user", "content": SEARCH_BUDGET_DONE} in json.loads(traj.raw)
    assert traj.answer == "Answer" and traj.citations == ["p:A"]
    assert sum(s.kind == "search" for s in traj.steps) == 1
    assert traj.n_llm_calls == len(llm.calls) == 3


def test_never_stopping_policy_matches_no_hook():
    script = ["Action: search[first]", "Action: search[second]", "Final: Answer | Cite: p:A,p:B"]
    base_retriever, hook_retriever = FakeRetriever(), FakeRetriever()
    base = ReActAgent().run("Question?", base_retriever, MockLLM(list(script)))
    hooked = ReActAgent(should_stop=lambda q, steps, n: False).run("Question?", hook_retriever, MockLLM(list(script)))
    assert hooked == base
    assert hook_retriever.calls == base_retriever.calls
    assert [call[0] for call in hook_retriever.calls] == ["first", "second"]


def test_policy_receives_question_steps_and_search_count():
    seen = []

    def policy(question, steps, n_searches):
        seen.append((question, [s.kind for s in steps], n_searches))
        return False

    llm = MockLLM(["Action: search[first]", "Action: search[second]", "Final: Answer | Cite: p:A"])
    ReActAgent(should_stop=policy).run("Question?", FakeRetriever(), llm)
    assert seen == [("Question?", ["search"], 1), ("Question?", ["search", "search"], 2)]
