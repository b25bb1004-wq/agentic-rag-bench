"""Metric definitions and exact result-row contract."""
import math

import pytest

from ragbench.judge import Judge
from ragbench.llm import MockLLM
from ragbench.metrics import bootstrap_ci, citation_pr, exact_match, f1, normalize_answer, score_row
from ragbench.schema import AttackCase, Item, Passage, Trajectory


@pytest.mark.parametrize('pred,gold,em,expected_f1', [
    ('The U.S.', 'us', 1, 1), ('a cat', 'the cat', 1, 1),
    ('red red blue', 'red blue blue', 0, 2 / 3),
    ('Denver Broncos', 'Broncos', 0, 2 / 3),
    ('yes indeed', 'yes', 0, 0), ('no', 'no answer', 0, 0),
    ('noanswer', 'noanswer today', 0, 0), ('YES', 'yes', 1, 1),
    ('no', 'yes', 0, 0), ('', '', 1, 0), ('', 'word', 0, 0),
])
def test_hotpot_metrics(pred, gold, em, expected_f1):
    assert exact_match(pred, gold) == em
    assert f1(pred, gold) == pytest.approx(expected_f1)


def test_normalize():
    assert normalize_answer('  The, A! AN\nBlue-cat. ') == 'bluecat'


@pytest.mark.parametrize('citations,gold,expected', [
    ([], ['a'], (0, 0)), (['a'], [], (0, 0)), ([], [], (0, 0)),
    (['a', 'a', 'b'], ['a', 'c', 'c'], (0.5, 0.5)),
    (['a'], ['a', 'b'], (1, 0.5)),
])
def test_citations(citations, gold, expected):
    assert citation_pr(citations, gold) == expected


def test_bootstrap():
    values = [0, 1, 2, 3, 4]
    mean, lo, hi = bootstrap_ci(values)
    assert mean == 2
    assert lo <= mean <= hi
    assert bootstrap_ci(values) == (mean, lo, hi)
    assert bootstrap_ci([1]) == (1, 1, 1)
    assert all(math.isnan(v) for v in bootstrap_ci([]))
    with pytest.raises(ValueError):
        bootstrap_ci(values, n_boot=0)


def row(item, traj, **kwargs):
    return score_row(run_id='run', agent='react', condition='C0', seed=2,
                     category='ignored', item_or_case=item, traj=traj, **kwargs)


def test_clean_row_and_missing_citation_text():
    item = Item('q', 'Question?', 'answer', ['p:a'], 'bridge', [])
    traj = Trajectory('q', item.question, 'answer', ['p:invented'], [], ['p:a'], n_llm_calls=3)
    llm = MockLLM(['SUPPORTED'])
    result = row(item, traj, judge=Judge(llm),
                 passages_by_id={'p:a': Passage('p:a', 'A', 'Secret evidence')})
    assert set(result) == set('run_id agent condition seed category case_id qid answer gold citations '
                              'retrieved_ids abstained parse_failed success em f1 cit_p cit_r supported followed n_llm_calls'.split())
    assert result['category'] == 'clean'
    assert result['case_id'] is None
    assert result['success'] is result['followed'] is None
    assert result['em'] == result['f1'] == 1
    assert result['cit_p'] == result['cit_r'] == 0
    assert result['supported'] is False
    assert result['n_llm_calls'] == 3
    assert 'Secret evidence' not in llm.calls[0][1]['content']
    assert '"passages": []' in llm.calls[0][1]['content']


def test_attack_null_gold_and_abstention():
    case = AttackCase('c', 'unsupported_claim', 'q', 'Q?', None)
    traj = Trajectory('q', 'Q?', 'UNKNOWN', [], [], [], abstained=True)
    llm = MockLLM(['SUPPORTED'])
    result = row(case, traj, judge=Judge(llm))
    assert result['success'] is False
    assert all(result[k] is None for k in ('em', 'f1', 'cit_p', 'cit_r', 'supported', 'followed'))
    assert not llm.calls


def test_counterfactual_dispatch_and_overrides():
    case = AttackCase('c', 'counterfactual', 'q', 'Q?', 'new',
                      meta={'original': 'old', 'substitute': 'new', 'gold_ids': ['p:a']})
    traj = Trajectory('q', 'Q?', 'new', ['p:a'], [], ['p:a'])
    result = row(case, traj)
    assert result['success'] is False
    assert result['followed'] is True
    assert result['cit_p'] == result['cit_r'] == 1
    assert row(case, traj, success_fn=lambda c, t: True,
               followed_fn=lambda c, t: False)['success'] is True


def test_real_citation_passage_text():
    item = Item('q', 'Q?', 'A', [], 'bridge', [])
    traj = Trajectory('q', 'Q?', 'A', ['p:a', 'p:a', 'p:b'], [], ['p:a', 'p:b'])
    llm = MockLLM(['SUPPORTED'])
    result = row(item, traj, judge=Judge(llm), passages_by_id={
        'p:a': Passage('p:a', 'A', 'Evidence'), 'p:b': 'More evidence'})
    assert result['supported'] is True
    assert llm.calls[0][1]['content'].count('"Evidence"') == 1
