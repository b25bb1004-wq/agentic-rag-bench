"""Offline execution, resume, controls, memory, and judge integration."""
from dataclasses import asdict
import json
from pathlib import Path

import pytest
import yaml

from ragbench import run as runner
from ragbench.llm import MockLLM
from ragbench.memory import Episode
from ragbench.metrics import score_row
from ragbench.schema import AttackCase, Item, Passage, Step, Trajectory


@pytest.fixture
def setup_run(monkeypatch, tmp_path):
    items = [Item(str(i), f'Where was person {i} born?', f'Town{i}', [f'p:Person{i}', f'p:Other{i}'], 'bridge',
                  [Passage(f'p:Person{i}', f'Person{i}', f'Person {i} was born in Town{i}.'),
                   Passage(f'p:Other{i}', f'Other{i}', f'Other evidence for person {i}.')])
             for i in range(8)]
    monkeypatch.setattr(runner, 'load_items', lambda: items)
    monkeypatch.setattr(runner, 'read_splits', lambda: {'eval': [i.qid for i in items], 'dev': ['7']})
    config = dict(name='test', agent='react', condition='c0', seeds=[0], n_clean=2,
                  n_per_category=1, workers=3, out_dir=str(tmp_path / 'results'))
    return config, items


def rows(config, name='seed0.jsonl'):
    return runner.read_rows(Path(config['out_dir']) / name)


@pytest.mark.parametrize('agent', ['react', 'plan'])
def test_mock_exact_keys_resume_and_controls(setup_run, agent):
    config, items = setup_run
    config['agent'] = agent
    result = runner.run(config, mock=True, limit=8)
    assert result['written'] == 8
    assert result['errors'] == 0
    first = rows(config)
    expected = score_row(run_id='test', agent=agent, condition='c0', seed=0, category='clean',
                         item_or_case=items[0], traj=Trajectory('0', 'Q', '', [], [], []))
    assert all(set(expected) <= set(row) for row in first)
    assert all(row['prompt_tokens_added'] == 0 for row in first)
    clean = {row['qid'] for row in first if row['category'] == 'clean'}
    assert len(clean) > 1  # Clean null case_ids must not collapse during resume.
    assert all(row['qid'] in clean for row in first if row['category'] != 'clean')
    assert all(row['n_llm_calls'] == 2 for row in first)
    assert any(row['citations'] for row in first)
    before = (Path(config['out_dir']) / 'seed0.jsonl').read_bytes()
    assert runner.run(config, mock=True, limit=8) == dict(written=0, errors=0, skipped=8)
    assert (Path(config['out_dir']) / 'seed0.jsonl').read_bytes() == before


def test_memory_only_c1(setup_run, monkeypatch, tmp_path):
    config, items = setup_run
    episode = Episode('train', 'a prior question', Trajectory('train', 'a prior question', 'memory answer', [],
                      [Step('search', 'prior search')], []), True)
    path = tmp_path / 'episodes.jsonl'
    path.write_text(json.dumps(asdict(episode)) + '\n')
    config['memory'] = dict(episodes_path=str(path), k=1)
    mocks = []

    def make_llm(config, mock):
        llm = MockLLM(['Action: search[person]', 'Final: answer | Cite: p:Person0'])
        mocks.append(llm)
        return llm

    monkeypatch.setattr(runner, 'make_llm', make_llm)
    for condition in ('c0', 'c1', 'c2', 'c1_poison_habit_k1', 'c2_poison_fact_k1'):
        config.update(condition=condition, out_dir=str(tmp_path / condition))
        assert runner.run(config, mock=True, limit=1)['written'] == 1
        system = mocks[-1].calls[0][0]['content']
        assert ('Past experience' in system) == condition.startswith('c1')
        if condition == 'c1':
            assert 'memory answer' in system and 'prior search' in system


def test_exception_continues_and_retry(setup_run, monkeypatch):
    config, _ = setup_run
    original = runner.HybridRetriever

    class BrokenRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, query, k, overlay):
            raise RuntimeError('injected failure')

    monkeypatch.setattr(runner, 'HybridRetriever', BrokenRetriever)
    result = runner.run(config, mock=True, limit=8)
    assert result['errors'] == 8 and result['written'] == 0
    errors = rows(config, 'errors.jsonl')
    assert len(errors) == 8
    assert all(e['error'] == 'injected failure' and e['phase'] == 'run' for e in errors)
    monkeypatch.setattr(runner, 'HybridRetriever', original)
    assert runner.run(config, mock=True, limit=8)['written'] == 8


def test_one_failure_preserves_other_rows(setup_run, monkeypatch):
    config, _ = setup_run
    execute = runner.execute_case

    def fail_one(config, seed, case, *args):
        if runner.case_key(case) == ('clean', '0'):
            raise ValueError('one bad case')
        return execute(config, seed, case, *args)

    monkeypatch.setattr(runner, 'execute_case', fail_one)
    result = runner.run(config, mock=True, limit=8)
    assert result['written'] == 7 and result['errors'] == 1


def test_list_six_categories_without_model_or_output(setup_run, monkeypatch, capsys):
    config, _ = setup_run
    monkeypatch.setattr(runner, 'HybridRetriever', lambda *a, **kw: pytest.fail('should not build index'))
    runner.run(config, mock=True, list_cases=True)
    line = capsys.readouterr().out
    for category in ('clean', *runner.REGISTRY):
        assert f'{category}=' in line
    assert not Path(config['out_dir']).exists()


def test_judge_keeps_raw_and_uses_overlay(setup_run, monkeypatch):
    config, items = setup_run
    out = Path(config['out_dir'])
    out.mkdir()
    base = items[0].passages[0]
    added = Passage(base.id, base.title, 'Changed case evidence')
    case = AttackCase('swap', 'counterfactual', '0', 'changed question', 'new', [added],
                      [items[0].passages[1].id])
    raw = dict(seed=0, category='counterfactual', case_id='swap', qid='0', answer='new',
               citations=[added.id, added.id, items[0].passages[1].id], retrieved_ids=[added.id], abstained=False, supported=None)
    source = out / 'seed0.jsonl'
    source.write_text(json.dumps(raw) + '\n')
    before = source.read_bytes()
    llm = MockLLM(['SUPPORTED'])
    monkeypatch.setattr(runner, 'LLM', lambda **kw: llm)
    assert runner.judge_rows(config, 0, [case], runner.build_corpus(items), out, False) == (1, 0)
    assert source.read_bytes() == before
    assert rows(config, 'seed0.judged.jsonl')[0]['supported'] is True
    prompt = json.loads(llm.calls[0][1]['content'])
    assert prompt['question'] == 'changed question'
    assert prompt['passages'] == ['Changed case evidence']


def test_judge_second_pass_and_abstention(setup_run, monkeypatch):
    config, _ = setup_run
    runner.run(config, mock=True, limit=8)
    raw_path = Path(config['out_dir']) / 'seed0.jsonl'
    raw = rows(config)
    raw[0]['abstained'] = True
    raw_path.write_text(''.join(json.dumps(r) + '\n' for r in raw))
    before = raw_path.read_bytes()
    monkeypatch.setattr(runner, 'HybridRetriever', lambda *a, **kw: pytest.fail('judge needs no retriever'))
    assert runner.run(config, mock=True, score_judge=True)['written'] == 8
    judged = rows(config, 'seed0.judged.jsonl')
    assert judged[0]['supported'] is None
    assert raw_path.read_bytes() == before


def test_seeds_split_and_limits(setup_run):
    config, items = setup_run
    config.update(seeds=[0, 1], split='dev', n_per_category=0)
    assert runner.run(config, mock=True)['written'] == 2
    assert rows(config)[0]['qid'] == '7'
    assert rows(config, 'seed1.jsonl')[0]['seed'] == 1
    for limit in range(10):
        cases = runner.build_cases(items, {**config, 'n_per_category': 1}, 0, limit)
        assert len(cases) <= limit
        controls = {c.qid for c in cases if isinstance(c, Item)}
        assert all(c.qid in controls for c in cases if isinstance(c, AttackCase))


def test_cli_and_emit_configs(setup_run, tmp_path, monkeypatch, capsys):
    config, _ = setup_run
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(config))
    runner.main(['--config', str(path), '--mock', '--limit', '8'])
    assert len(rows(config)) == 8
    runner.main(['--config', str(path), '--list-cases'])
    assert 'counterfactual=' in capsys.readouterr().out
    directory = tmp_path / 'configs'
    directory.mkdir()
    for agent in ('react', 'plan'):
        for condition in ('c1', 'c2'):
            (directory / f'{agent}_{condition}.yaml').write_text(yaml.safe_dump({**config, 'agent': agent, 'condition': condition}))
    runner.emit_poison_configs(directory)
    generated = list(directory.glob('*poison*.yaml'))
    assert len(generated) == 24
    for path in generated:
        emitted = yaml.safe_load(path.read_text())
        runner.validate_config(emitted)
        assert emitted['out_dir'] == f"results/{emitted['name']}"


@pytest.mark.parametrize('change', [dict(agent='bad'), dict(condition='c1_bad'), dict(workers=0),
                                   dict(n_clean=-1), dict(seeds=[0, 0])])
def test_invalid_config(setup_run, change):
    config, _ = setup_run
    with pytest.raises(ValueError):
        runner.run({**config, **change}, mock=True)


def test_mock_disables_dense_model_and_progress(setup_run, monkeypatch, capsys):
    config, items = setup_run
    config.update(n_clean=8, n_per_category=5, retriever={'dense_model': 'unused-local-model'})
    original = runner.HybridRetriever

    def construct(passages, dense_model):
        assert dense_model is None
        return original(passages)

    monkeypatch.setattr(runner, 'HybridRetriever', construct)
    result = runner.run(config, mock=True)
    assert result['written'] == 33 and result['errors'] == 0
    assert 'cases=25' in capsys.readouterr().out


def test_fact_poison_loads_seeded_episodes(setup_run, tmp_path):
    config, items = setup_run
    path = tmp_path / 'episodes.jsonl'
    path.write_text('')
    config.update(condition='c1_poison_fact_k5', memory={'episodes_path': str(path), 'k': 5})
    first = runner.make_memory(config, items, 3)
    second = runner.make_memory(config, items, 3)
    assert len(first.episodes) == 5
    assert [asdict(e) for e in first.episodes] == [asdict(e) for e in second.episodes]
    answers = {item.qid: item.answer for item in items}
    assert all(ep.trajectory.answer != answers[ep.qid] for ep in first.episodes)


def test_c2_fact_poison_measurement_without_retrieval_memory(setup_run):
    config, _ = setup_run
    config['condition'] = 'c2_poison_fact_k5'
    config['n_clean'] = 8
    config['n_per_category'] = 0
    assert runner.run(config, mock=True)['errors'] == 0
    targets = [r for r in rows(config) if 'fact_substitute' in r]
    assert len(targets) == 5
    assert all(r['fact_success'] is False for r in targets)
