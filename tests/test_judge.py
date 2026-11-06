"""Support parsing and human validation use scripted LLMs only."""
import json
import math

import pytest

from ragbench.judge import Judge
from ragbench.llm import MockLLM


@pytest.mark.parametrize('reply,expected,unparseable', [
    ('SUPPORTED', True, 0), ('NOT_SUPPORTED', False, 0), ('garbage', False, 1),
    ('supported', True, 0), ('not_supported', False, 0), ('', False, 1),
    ('  SUPPORTED\nExplanation', True, 0), ('SUPPORTEDNESS', False, 1),
    ('SUPPORTED.', True, 0),
])
def test_parse(reply, expected, unparseable):
    class RecordingMock(MockLLM):
        def chat(self, messages, max_tokens=256, temperature=1, seed=0):
            assert temperature == 0
            return super().chat(messages, max_tokens, temperature, seed)
    judge = Judge(RecordingMock([reply]))
    assert judge.supported('Q?', 'A', ['Evidence']) is expected
    assert judge.unparseable == unparseable


def test_no_evidence():
    assert Judge(MockLLM(['SUPPORTED'])).supported('Q', 'A', []) is False


def test_validate_known_kappa(tmp_path):
    fixture = tmp_path / 'labels.jsonl'
    labels = [True, True, True, False, False, False]
    fixture.write_text(''.join(json.dumps(dict(question='Q', answer='A', passages=['P'], label=v))
                               + '\n' for v in labels))
    judge = Judge(MockLLM(['SUPPORTED', 'SUPPORTED', 'NOT_SUPPORTED',
                         'SUPPORTED', 'NOT_SUPPORTED', 'NOT_SUPPORTED']))
    result = judge.validate(fixture)
    assert result['n'] == 6
    assert result['accuracy'] == pytest.approx(2 / 3)
    assert result['kappa'] == pytest.approx(1 / 3)
    assert result['confusion_matrix'] == dict(tp=2, tn=2, fp=1, fn=1)


def test_empty_validation(tmp_path):
    fixture = tmp_path / 'empty.jsonl'
    fixture.write_text('')
    result = Judge(MockLLM([])).validate(fixture)
    assert result['n'] == 0
    assert math.isnan(result['accuracy']) and math.isnan(result['kappa'])
