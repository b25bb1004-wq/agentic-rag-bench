import json
import pytest

from ragbench.agents.common import SYSTEM_PROMPT, build_system
from ragbench.memory import Episode, select_episodes
from ragbench.schema import Trajectory
from ragbench.sft import build_sft, read_jsonl, write_jsonl


def test_shared_selection_and_memory_removal(tmp_path):
    messages = [{'role': 'system', 'content': build_system('SECRET MEMORY', 'EXTRA')}, {'role': 'user', 'content': 'question'}, {'role': 'assistant', 'content': 'Action: search[query]'}, {'role': 'user', 'content': 'Observation: evidence'}, {'role': 'assistant', 'content': 'Final: answer | Cite: p:source'}]
    episodes = [Episode(qid, 'question', Trajectory(qid, 'question', 'answer', [], [], [], json.dumps(messages)), correct) for qid, correct in [('b', True), ('a', True), ('c', False)]]
    records = build_sft(episodes)
    assert len(records) == len(select_episodes(episodes)) == 2
    for row in records:
        assert row['messages'][0] == {'role': 'system', 'content': SYSTEM_PROMPT}
        assert row['messages'][1:] == messages[1:]
        assert 'SECRET MEMORY' not in json.dumps(row)
    assert 'SECRET MEMORY' in episodes[0].trajectory.raw
    path = tmp_path / 'sft.jsonl'
    write_jsonl(records, path)
    assert read_jsonl(path) == records
    assert build_sft([]) == []


def test_invalid_conversation():
    episode = Episode('x', 'q', Trajectory('x', 'q', '', [], [], [], '{}'), True)
    with pytest.raises(ValueError):
        build_sft([episode])
