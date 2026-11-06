"""Agent contract tests using scripted model replies and local passages."""
import json

import pytest

from ragbench.agents import PlanAgent, ReActAgent
from ragbench.agents.common import SYSTEM_PROMPT, build_system, clip_reply, format_obs, parse_final, parse_search
from ragbench.llm import MockLLM
from ragbench.schema import Passage, Step


class FakeRetriever:
    def __init__(self):
        self.calls = []
        self.results = [(Passage("p:A", "A", "First evidence."), 1.0),
                        (Passage("p:B", "B", "Second evidence."), 0.5)]

    def search(self, query, k=5, overlay=None):
        self.calls.append((query, k, overlay))
        return self.results[:k]


def assert_raw(traj, final_reply):
    messages = json.loads(traj.raw)
    assert messages[-1] == {"role": "assistant", "content": final_reply}
    assert all(set(message) == {"role", "content"} for message in messages)
    return messages


def test_react_happy_path():
    retriever = FakeRetriever()
    reply = "Final: Answer | Cite: p:A,p:B"
    llm = MockLLM(["Thought: Find evidence.\nAction: search[first]", reply])
    traj = ReActAgent().run("Question?", retriever, llm)
    assert (traj.answer, traj.citations, traj.abstained) == ("Answer", ["p:A", "p:B"], False)
    assert traj.retrieved_ids == ["p:A", "p:B"]
    obs = "[p:A] First evidence.\n[p:B] Second evidence."
    assert traj.steps == [Step("search", "first", obs), Step("answer", "Answer", "")]
    assert traj.n_llm_calls == len(llm.calls) == 2
    assert retriever.calls == [("first", 3, None)]
    assert assert_raw(traj, reply)[3] == {"role": "user", "content": "Observation: " + obs}


def test_react_rejects_final_before_search():
    retriever = FakeRetriever()
    premature = "Final: Invented | Cite: 1,2"
    reply = "Final: Answer | Cite: p:A"
    llm = MockLLM([premature, "Action: search[evidence]", reply])
    traj = ReActAgent().run("Question?", retriever, llm)
    assert traj.answer == "Answer" and traj.citations == ["p:A"]
    assert not traj.parse_failed and not traj.abstained
    assert traj.retrieved_ids == ["p:A", "p:B"]
    assert traj.n_llm_calls == len(llm.calls) == 3
    messages = assert_raw(traj, reply)
    assert messages[2] == {"role": "assistant", "content": premature}
    assert messages[3] == {
        "role": "user",
        "content": "You must call search[<query>] at least once before giving Final. Search now.",
    }
    assert messages[3] in llm.calls[1]


@pytest.mark.parametrize("reply", ["Final: Answer | Cite: 1", "Final: UNKNOWN | Cite:", "Thinking"])
def test_react_search_budget_failure(reply):
    retriever = FakeRetriever()
    llm = MockLLM([reply])
    traj = ReActAgent(max_steps=2).run("Question?", retriever, llm)
    assert traj.parse_failed and not traj.abstained
    assert traj.answer == "" and traj.citations == []
    assert traj.retrieved_ids == [] and retriever.calls == []
    assert traj.steps == [Step("answer", "", "")]
    assert traj.n_llm_calls == len(llm.calls) == 2


def test_react_min_searches_zero_accepts_immediate_final():
    retriever = FakeRetriever()
    llm = MockLLM(["Final: Answer | Cite: 1"])
    traj = ReActAgent(min_searches=0).run("Question?", retriever, llm)
    assert traj.answer == "Answer" and not traj.parse_failed
    assert traj.n_llm_calls == 1 and retriever.calls == []


def test_react_min_searches_two_requires_both_searches():
    llm = MockLLM(["Action: search[one]", "Final: Early | Cite: p:A",
                   "Action: search[two]", "Final: Answer | Cite: p:A"])
    retriever = FakeRetriever()
    traj = ReActAgent(min_searches=2).run("Question?", retriever, llm)
    assert traj.answer == "Answer" and not traj.parse_failed
    assert len(retriever.calls) == 2 and traj.n_llm_calls == 4


@pytest.mark.parametrize("agent", [ReActAgent(), PlanAgent()])
def test_empty_retrieval_is_valid_and_prompt_teaches_ids(agent):
    retriever = FakeRetriever()
    retriever.results = []
    llm = MockLLM(["Q: evidence\nAction: search[evidence]", "Final: UNKNOWN | Cite:"])
    traj = agent.run("Question?", retriever, llm)
    assert traj.abstained and not traj.parse_failed
    assert traj.retrieved_ids == [] and len(retriever.calls) == 1
    prompt = llm.calls[0][0]["content"]
    assert "Final: Example answer | Cite: p:Some Title" in prompt
    assert "Never cite a number or an id you have not seen in an Observation. Do not answer from memory." in prompt


def test_react_default_budget_allows_nudge_and_four_searches():
    llm = MockLLM(["Final: Early | Cite: 1"] + ["Action: search[evidence]"] * 4
                  + ["Final: Answer | Cite: p:A"])
    traj = ReActAgent().run("Question?", FakeRetriever(), llm)
    assert traj.answer == "Answer" and not traj.parse_failed
    assert traj.n_llm_calls == 6


@pytest.mark.parametrize("agent", [ReActAgent(), PlanAgent()])
def test_abstain(agent):
    traj = agent.run("Question?", FakeRetriever(), MockLLM(["Action: search[evidence]", "Final: UNKNOWN | Cite:"]))
    assert traj.abstained
    assert traj.answer == "UNKNOWN"
    assert traj.citations == []


@pytest.mark.parametrize("agent,script", [
    (ReActAgent(), ["Action: search[evidence]", "Final: Answer | Cite: p:invented"]),
    (PlanAgent(), ["Q: evidence", "Final: Answer | Cite: p:invented"]),
])
def test_hallucinated_citation_is_preserved(agent, script):
    traj = agent.run("Question?", FakeRetriever(), MockLLM(script))
    assert traj.citations == ["p:invented"]
    assert "p:invented" not in traj.retrieved_ids


@pytest.mark.parametrize("forced,answer,abstained", [
    ("Still thinking", "", False), ("Final: Answer | Cite:", "Answer", False),
])
def test_react_forced_final(forced, answer, abstained):
    llm = MockLLM(["Thinking", "Thinking again", forced])
    traj = ReActAgent(max_steps=2, min_searches=0).run("Question?", FakeRetriever(), llm)
    assert traj.n_llm_calls == len(llm.calls) == 3
    assert (traj.answer, traj.abstained, traj.citations) == (answer, abstained, [])
    messages = assert_raw(traj, forced)
    assert messages[-2]["content"] == "Give your Final answer now."
    assert messages[3]["content"] == "Reply with either Action: search[<query>] or Final: <short answer> | Cite: <ids>"
    assert messages[5]["content"] == "Reply with either Action: search[<query>] or Final: <short answer> | Cite: <ids>"
    assert traj.steps == [Step("answer", answer, "")]


def test_build_system():
    assert build_system("", "") == SYSTEM_PROMPT
    assert build_system("memory", "extra") == SYSTEM_PROMPT + "\n\nPast experience (may help):\nmemory\n\nextra"
    assert build_system("", "extra") == SYSTEM_PROMPT + "\n\nextra"
    assert build_system("memory", "") == SYSTEM_PROMPT + "\n\nPast experience (may help):\nmemory"


@pytest.mark.parametrize("agent,script", [
    (ReActAgent(), ["Action: search[one]", "Action: search[two]", "Final: Answer | Cite: p:A"]),
    (PlanAgent(), ["Q: one\nQ: two", "Final: Answer | Cite: p:A"]),
])
def test_overlay_memory_seed_and_deduplication(agent, script):
    retriever = FakeRetriever()
    overlay = object()
    params = []

    class RecordingMock(MockLLM):
        def chat(self, messages, max_tokens=256, temperature=0.0, seed=0, stop=None):
            params.append((max_tokens, temperature, seed, stop))
            return super().chat(messages, max_tokens, temperature, seed, stop)

    traj = agent.run("Question?", retriever, RecordingMock(script), "memory", "extra", overlay, 42)
    assert all(call[2] is overlay for call in retriever.calls)
    assert traj.retrieved_ids == ["p:A", "p:B"]
    assert json.loads(traj.raw)[0]["content"] == build_system("memory", "extra")
    assert params == [(200, 0.0, 42, ["\nObservation:", "Observation:"])] * traj.n_llm_calls


def test_plan_happy_path_and_limit():
    retriever = FakeRetriever()
    reply = "Final: Answer | Cite: p:B"
    llm = MockLLM(["Q: first\nQ: second\nQ: third\nQ: ignored", reply])
    traj = PlanAgent(k=1, max_sub=2).run("Question?", retriever, llm)
    assert retriever.calls == [("first", 1, None), ("second", 1, None)]
    assert traj.answer == "Answer"
    assert traj.citations == ["p:B"]
    assert traj.retrieved_ids == ["p:A"]
    assert [step.kind for step in traj.steps] == ["plan", "search", "plan", "search", "answer"]
    assert [step.arg for step in traj.steps[:4]] == ["first", "first", "second", "second"]
    assert traj.n_llm_calls == len(llm.calls) == 2
    messages = assert_raw(traj, reply)
    assert len(messages) == 5
    assert messages[2]["content"].startswith("Q: first")
    assert "Question?" in messages[3]["content"]
    assert messages[3]["content"].count("Observation: [p:A] First evidence.") == 2


def test_plan_fallback_and_unparseable_final():
    retriever = FakeRetriever()
    traj = PlanAgent().run("Original question?", retriever, MockLLM(["No plan", "No answer"]))
    assert retriever.calls == [("Original question?", 3, None)]
    assert traj.steps[0] == Step("plan", "Original question?", "")
    assert (traj.answer, traj.citations, traj.abstained, traj.n_llm_calls) == ("", [], False, 5)
    assert traj.parse_failed
    assert_raw(traj, "No answer")


@pytest.mark.parametrize("text,expected", [
    ("  Final:  Answer  |  Cite: p:A, p:B", ("Answer", ["p:A", "p:B"], False)),
    ("Thought: done\nFinal: unknown | Cite:", ("unknown", [], True)),
    ("Final: | Cite:", ("", [], True)),
    ("Final: Answer", ("Answer", [], False)),
    ("No final here", None),
    ("Final: Answer\n| Cite: p:A", ("Answer", ["p:A"], False)),
])
def test_parse_final(text, expected):
    assert parse_final(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Thought: search\nAction: search[  some [nested] query  ]", "some [nested] query"),
    ("search[first]\nsearch[second]", None),
    ("search[missing", None),
    ("search[broken\nquery]", None),
    ("No action", None),
])
def test_parse_search(text, expected):
    assert parse_search(text) == expected


def test_format_obs_limits():
    results = [(Passage(f"p:{i}", str(i), "x" * 650), 1.0) for i in range(4)]
    assert format_obs(results) == "\n".join(f"[p:{i}] " + "x" * 600 for i in range(3))
    assert format_obs([]) == ""


@pytest.mark.parametrize("text,expected", [
    ("No marker  \n", "No marker"),
    ("Observation: invented", ""),
    ("  Observation: invented", ""),
    ("search[first]\nObservation: fake\nObservation: more", "search[first]"),
    ("search[first] \tObservation: fake", "search[first]"),
    ("xObservation: keep", "xObservation: keep"),
    ("observation: keep", "observation: keep"),
])
def test_clip_reply(text, expected):
    assert clip_reply(text) == expected


@pytest.mark.parametrize("agent", [ReActAgent(), PlanAgent()])
@pytest.mark.parametrize("first", [
    "Action: search[evidence]\nObservation: fabricated\nFinal: Invented | Cite: p:fake",
    "Action: search[evidence]\nFinal: Invented | Cite: p:fake",
    "Final: Invented | Cite: p:fake\nAction: search[evidence]",
])
def test_search_precedes_final_and_clips_history(agent, first):
    retriever = FakeRetriever()
    final = "Final: Answer | Cite: p:A"
    llm = MockLLM([first, final + "\nObservation: another fabrication"])
    traj = agent.run("Question?", retriever, llm)
    assert traj.answer == "Answer" and not traj.parse_failed
    assert retriever.calls == [("evidence", 3, None)]
    assistants = [m["content"] for m in json.loads(traj.raw) if m["role"] == "assistant"]
    assert assistants == [clip_reply(first), final]
    assert all("Observation:" not in reply for reply in assistants)
    assert any(m["content"] == clip_reply(first) for m in llm.calls[1])


def test_observation_at_start_nudges_without_accepting_fake_final():
    llm = MockLLM(["Observation: fake\nFinal: Invented | Cite: p:fake",
                   "Action: search[evidence]", "Final: Answer | Cite: p:A"])
    traj = ReActAgent().run("Question?", FakeRetriever(), llm)
    messages = json.loads(traj.raw)
    assert messages[2] == {"role": "assistant", "content": ""}
    assert messages[3]["content"] == "Reply with either Action: search[<query>] or Final: <short answer> | Cite: <ids>"
    assert traj.answer == "Answer" and traj.n_llm_calls == 3


def test_react_forced_turn_ignores_search_and_parses_final():
    retriever = FakeRetriever()
    llm = MockLLM(["Action: search[first]",
                   "Action: search[second]\nFinal: Invented | Cite: p:A\nObservation: fake"])
    stops = []

    class RecordingMock(MockLLM):
        def chat(self, messages, max_tokens=256, temperature=0.0, seed=0, stop=None):
            stops.append(stop)
            return llm.chat(messages, max_tokens, temperature, seed, stop)

    traj = ReActAgent(max_steps=1).run("Question?", retriever, RecordingMock([]))
    assert [call[0] for call in retriever.calls] == ["first"]
    assert not traj.parse_failed and traj.answer == "Invented" and traj.n_llm_calls == 2
    assert stops == [["\nObservation:", "Observation:"]] * 2


def test_plan_final_turn_search_gets_real_observation_before_answer():
    retriever = FakeRetriever()
    llm = MockLLM(["Q: first\nObservation: fake",
                   "Action: search[second]\nFinal: Invented | Cite: p:fake\nObservation: fake",
                   "Final: Answer | Cite: p:A"])
    traj = PlanAgent().run("Question?", retriever, llm)
    assert [call[0] for call in retriever.calls] == ["first", "second"]
    assert traj.answer == "Answer" and not traj.parse_failed and traj.n_llm_calls == 3
    assert all("Observation:" not in m["content"] for m in json.loads(traj.raw) if m["role"] == "assistant")


def test_plan_repeated_searches_are_bounded():
    retriever = FakeRetriever()
    traj = PlanAgent(max_sub=1).run("Question?", retriever, MockLLM([
        "Q: first", "Action: search[more]\nFinal: Invented | Cite: p:A"]))
    assert not traj.parse_failed and traj.answer == "Invented"
    assert traj.n_llm_calls == 3 and len(retriever.calls) == 2


@pytest.mark.parametrize('separator', [' | ', '. ', '\n', '; ', ', ', ' ', ''])
def test_tolerant_final_separators(separator):
    assert parse_final('Final: A' + separator + 'Cite: p:X, p:Y') == (
        'A', ['p:X', 'p:Y'], False)


@pytest.mark.parametrize('text,expected', [
    ('Final: A\nExplanation follows.', ('A', [], False)),
    ('fInAl: A. cItE: p:Austin, Texas, p:Monsters, Inc.',
     ('A', ['p:Austin, Texas', 'p:Monsters, Inc.'], False)),
    ('Final: Old | Cite: p:Old\nFINAL: New', ('New', [], False)),
    ('Final: Old\nfinal: New; cite: p:New', ('New', ['p:New'], False)),
    ('Final: Unknown.', ('Unknown', [], True)),
    ('Final: Unknown. Cite:', ('Unknown', [], True)),
    ('Final: UNKNOWN | Cite:', ('UNKNOWN', [], True)),
])
def test_tolerant_final_last_marker_and_abstention(text, expected):
    assert parse_final(text) == expected


@pytest.mark.parametrize('agent', [ReActAgent(), PlanAgent()])
def test_missing_citation_is_measured_as_successful_parse(agent):
    result = agent.run('Question?', FakeRetriever(), MockLLM([
        'Action: search[evidence]', 'Final: A']))
    assert result.answer == 'A' and result.citations == []
    assert not result.parse_failed and not result.abstained


@pytest.mark.parametrize('agent', [ReActAgent(), PlanAgent()])
def test_duplicate_search_uses_existing_evidence(agent):
    retriever = FakeRetriever()
    llm = MockLLM(['Action: search[Some Evidence]',
                   'Action: search[  SOME   evidence ]',
                   'Final: A | Cite: p:A'])
    result = agent.run('Question?', retriever, llm)
    assert [call[0] for call in retriever.calls] == ['Some Evidence']
    assert [s.arg for s in result.steps if s.kind == 'search'] == ['Some Evidence']
    assert result.answer == 'A' and result.n_llm_calls == 3
    assert not result.parse_failed
    assert json.loads(result.raw)[-2] == {
        'role': 'user',
        'content': 'You already searched that. Use the evidence above and give Final: <short answer> | Cite: <ids>',
    }


def test_plan_duplicate_subquestions_do_not_add_steps():
    retriever = FakeRetriever()
    result = PlanAgent().run('Question?', retriever, MockLLM([
        'Q: Some Evidence\nQ: SOME   evidence', 'Final: A']))
    assert len(retriever.calls) == 1
    assert [s.kind for s in result.steps] == ['plan', 'search', 'answer']
    assert any(m['content'].startswith('You already searched that.') for m in json.loads(result.raw))


@pytest.mark.parametrize('agent', [ReActAgent(), PlanAgent()])
def test_invalid_reply_gets_explicit_nudge(agent):
    result = agent.run('Question?', FakeRetriever(), MockLLM([
        'Action: search[evidence]', 'Still thinking', 'Final: A']))
    assert result.answer == 'A' and not result.parse_failed
    assert json.loads(result.raw)[-2] == {
        'role': 'user',
        'content': 'Reply with either Action: search[<query>] or Final: <short answer> | Cite: <ids>',
    }


@pytest.mark.parametrize('agent', [ReActAgent(), PlanAgent()])
def test_only_first_action_in_reply_is_executed(agent):
    retriever = FakeRetriever()
    result = agent.run('Question?', retriever, MockLLM([
        'Action: search[first]\nAction: search[second]', 'Final: A']))
    assert [call[0] for call in retriever.calls] == ['first']
    assert result.answer == 'A'


@pytest.mark.parametrize('agent', [ReActAgent(), PlanAgent()])
def test_prompt_requires_short_answer(agent):
    llm = MockLLM(['Action: search[evidence]', 'Final: A'])
    agent.run('Question?', FakeRetriever(), llm)
    prompt = llm.calls[0][0]['content']
    assert 'Final: <short answer> | Cite: <id1>, <id2>' in prompt
    assert 'a name, number, date, place, or exactly\nyes or no for yes/no questions, with no explanation.' in prompt


def test_react_search_budget_stops_extra_searches():
    from ragbench.agents.react import SEARCH_BUDGET_DONE
    retriever = FakeRetriever()
    reply = "Final: Answer | Cite: p:A"
    llm = MockLLM(["Action: search[first]", "Action: search[second]", reply])
    traj = ReActAgent(max_searches=1).run("Question?", retriever, llm)
    assert [call[0] for call in retriever.calls] == ["first"]
    assert {"role": "user", "content": SEARCH_BUDGET_DONE} in json.loads(traj.raw)
    assert traj.answer == "Answer" and sum(s.kind == "search" for s in traj.steps) == 1
