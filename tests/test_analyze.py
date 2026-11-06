"""End-to-end summaries on explicit hand-made result rows."""
import csv
import json
import subprocess
import sys

import pytest

from ragbench.analyze import analyze, summarize


def make_row(qid, category='clean', condition='C0', **kwargs):
    return dict(agent='react', condition=condition, category=category, seed=0,
                qid=qid, gold='answer', **kwargs)


def test_twelve_row_cli(tmp_path):
    rows = []
    for i in range(4):
        rows.append(make_row(str(i), em=1, f1=1, success=None))
        rows.append(make_row(str(i), 'injection', em=i % 2, f1=0.5, success=i % 2 == 0,
                             cit_p=0.5, cit_r=1, supported=False))
        rows.append(make_row(str(i), 'counterfactual', 'C1_poison_k5', em=0.25, f1=0.5,
                             success=False, followed=True))
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'run.jsonl').write_text('\n'.join(map(json.dumps, rows)) + '\nnot json\n')
    out = tmp_path / 'custom.md'
    process = subprocess.run([sys.executable, '-m', 'ragbench.analyze', str(tmp_path),
                              '--out', str(out)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    text = out.read_text()
    assert 'Valid rows: 12. Malformed lines skipped: 1.' in text
    assert '| react | C0 | injection | 4 | 0.5000 | 0.5000 | 0.5000 [' in text
    assert 'Condition base (k=0)' not in text  # Legacy label has no valid poison pairing.
    assert 'Primary endpoints' in text
    with (tmp_path / 'summary.csv').open() as source:
        records = list(csv.DictReader(source))
    injection = next(r for r in records if r['category'] == 'injection')
    assert injection['utility_under_attack'] == '0.5000'
    assert injection['cit_p'] == '0.5000'
    assert injection['cit_r'] == '1.0000'
    assert 'asr_excess' not in injection
    assert injection['clean_em'] == '1.0000'
    counterfactual = next(r for r in records if r['category'] == 'counterfactual')
    assert counterfactual['followed'] == '1.0000'


def test_clean_diagnostics_use_matching_agent_condition_and_seed():
    rows = [make_row('a', em=1, abstained=False, parse_failed=False, citations=['p:a'], retrieved_ids=['p:a']),
            make_row('b', em=0, abstained=True, parse_failed=True, citations=['p:fake'], retrieved_ids=[]),
            make_row('a', 'injection', success=True)]
    rows.append({**rows[0], 'seed': 1, 'em': 0})
    rows.append({**rows[0], 'agent': 'plan', 'em': 0})
    r = next(r for r in summarize(rows) if r['category'] == 'injection')
    assert r['clean_em'] == r['clean_abstain_rate'] == r['clean_parse_failure_rate'] == 0.5
    assert r['clean_unretrieved_citation_rate'] == 0.5
    assert 'asr_excess' not in r and 'clean_control_rate' not in r


def test_empty_and_malformed(tmp_path):
    (tmp_path / 'bad.jsonl').write_text('null\n{}\n[]\n')
    result = analyze(tmp_path)
    assert result['rows'] == 0 and result['malformed'] == 3
    assert 'n/a' in (tmp_path / 'summary.md').read_text()


def test_nulls_and_unanswerable_excluded():
    rows = [make_row('q', 'unsupported_claim', em=None, f1=None, supported=None)]
    rows[0]['gold'] = None
    r = summarize(rows)[0]
    assert r['utility_under_attack'] is r['supported'] is r['asr'] is None
