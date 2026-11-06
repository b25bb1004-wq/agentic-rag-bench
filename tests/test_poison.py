import json

import pytest

from ragbench.memory import RetrievalMemory, select_episodes
from ragbench.poison import make_poison_episodes, habit_success, fact_success, poison_targets
from ragbench.schema import Item, Step, Trajectory
from ragbench.sft import build_sft


def targets():
    return [Item(str(i), f'Question {i}?', answer, [], 'bridge', []) for i, answer in enumerate(['Paris', 'Berlin', 'Tokyo'])]


@pytest.mark.parametrize('kind', ['habit', 'fact'])
def test_counts_selection_and_determinism(kind):
    episodes = make_poison_episodes(kind, 3, 12, targets())
    assert episodes == make_poison_episodes(kind, 3, 12, targets())
    assert len(episodes) == len(select_episodes(episodes)) == len(build_sft(episodes)) == 3
    if kind == 'fact':
        assert poison_targets(episodes) == {ep.qid: ep.trajectory.answer for ep in episodes}
        for item, episode in zip(targets(), episodes):
            assert episode.qid == episode.trajectory.qid == item.qid
            assert episode.question == item.question
            assert episode.trajectory.answer != item.answer
            assert fact_success(item, episode.trajectory.answer, episode.trajectory)
    else:
        assert all(habit_success(ep.trajectory) for ep in episodes)
        assert all(ep.trajectory.retrieved_ids and ep.trajectory.steps[0].kind == "search" for ep in episodes)


@pytest.mark.parametrize('kind', ['habit', 'fact'])
def test_poison_search_conversation_and_memory(kind):
    episodes = make_poison_episodes(kind, 3, 12, targets())
    records = build_sft(episodes)
    for episode, record in zip(episodes, records):
        trajectory = episode.trajectory
        observation = '[p:Reference] Reference evidence.'
        assert trajectory.steps == [Step('search', episode.question, observation),
                                    Step('answer', trajectory.answer)]
        assert trajectory.retrieved_ids == ['p:Reference']
        assert trajectory.n_llm_calls == 2
        messages = json.loads(trajectory.raw)
        assert [message['role'] for message in messages] == [
            'system', 'user', 'assistant', 'user', 'assistant']
        assert messages[1]['content'] == episode.question
        assert messages[2]['content'] == f'Action: search[{episode.question}]'
        assert messages[3]['content'] == f'Observation: {observation}'
        assert messages[-1]['content'] == (
            f'Final: {trajectory.answer} | Cite: {trajectory.citations[0]}')
        assert record['messages'] == messages
        assert RetrievalMemory([episode]).retrieve(episode.question) == (
            f'Q: {episode.question} | searches: {episode.question} | '
            f'Final: {trajectory.answer} | Cite: {trajectory.citations[0]}')


def test_success_predicates():
    traj = Trajectory('', '', 'Berlin', ['p:Source_3'], [], [])
    assert habit_success(traj)
    traj.steps.append(Step('search', 'query'))
    assert habit_success(traj)
    traj.steps.clear()
    traj.citations.clear()
    assert not habit_success(traj)
    assert fact_success(targets()[0], 'Berlin', traj)
    assert not fact_success(targets()[0], 'Tokyo', traj)
    assert not fact_success(targets()[1], 'Berlin', traj)
    traj.abstained = True
    assert not fact_success(targets()[0], 'Berlin', traj)


def test_invalid_and_generic():
    assert len(make_poison_episodes('habit', 5, 0)) == 5
    assert make_poison_episodes('fact', 0, 0) == []
    for kind, k, items in [('bad', 1, []), ('habit', -1, []), ('fact', 1, []), ('fact', 1, targets()[:1])]:
        with pytest.raises(ValueError):
            make_poison_episodes(kind, k, 0, items)


@pytest.mark.parametrize('kind', ['habit', 'fact'])
def test_plan_format_poison_matches_plan_agent_turns(kind):
    from ragbench.agents.plan import FINAL_ASK, PLAN_ASK
    episodes = make_poison_episodes(kind, 2, 0, targets=targets(), agent='plan')
    for ep in episodes:
        messages = json.loads(ep.trajectory.raw)
        assert messages[1]['content'].endswith(PLAN_ASK)
        assert messages[2]['content'].startswith('Q: ')
        assert messages[3]['content'].endswith(FINAL_ASK)
        assert messages[4]['content'].startswith('Final: ')
        assert [s.kind for s in ep.trajectory.steps] == ['plan', 'search', 'answer']
    assert len(build_sft(episodes)) == 2
    react = make_poison_episodes(kind, 2, 0, targets=targets())
    assert [e.trajectory.answer for e in react] == [e.trajectory.answer for e in episodes]


def test_poison_rejects_unknown_agent():
    with pytest.raises(ValueError, match='agent'):
        make_poison_episodes('habit', 1, 0, agent='other')
