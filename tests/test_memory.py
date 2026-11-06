from ragbench.memory import Episode, RetrievalMemory, select_episodes
from ragbench.schema import Step, Trajectory


def episode(qid, question, correct=True):
    return Episode(qid, question, Trajectory(qid, question, 'answer', [], [Step('search', 'query')], []), correct)


def test_selection():
    episodes = [episode('b', 'two'), episode('a', 'one'), episode('c', 'bad', False)]
    assert [ep.qid for ep in select_episodes(episodes)] == ['a', 'b']
    assert [ep.qid for ep in select_episodes(episodes, 1)] == ['b']
    assert select_episodes(episodes, 0) == []


def test_retrieval_and_mutation():
    episodes = [episode('a', 'astronomy stars'), episode('b', 'cooking food'), episode('c', 'football sports')]
    memory = RetrievalMemory(episodes, k=1)
    assert memory.retrieve('astronomy') == 'Q: astronomy stars | searches: query | Final: answer | Cite: '
    assert memory.retrieve('cooking').startswith('Q: cooking')
    memory.add(episode('d', 'penguin nesting'))
    assert memory.retrieve('penguin').startswith('Q: penguin')
    memory.remove('d')
    assert 'penguin' not in memory.retrieve('penguin')
    assert memory.retrieve('unmatched') == memory.retrieve('unmatched')
    assert len(RetrievalMemory(episodes, k=2).retrieve('stars').splitlines()) == 2
    assert RetrievalMemory([]).retrieve('anything') == ''
    assert RetrievalMemory([episode('bad', 'anything', False)]).retrieve('anything') == ''
    for ep in episodes:
        memory.remove(ep.qid)
    assert memory.retrieve('astronomy') == ''
