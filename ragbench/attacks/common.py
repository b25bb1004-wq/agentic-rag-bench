"""Shared deterministic attack helpers."""
from collections import Counter
import hashlib
import random
import re
import string

from ragbench.schema import Item


def normalize(s: str) -> str:
    """Official HotpotQA answer normalization."""
    lowered = s.lower()
    no_punctuation = ''.join(c for c in lowered if c not in string.punctuation)
    no_articles = re.sub(r'\b(a|an|the)\b', ' ', no_punctuation)
    return ' '.join(no_articles.split())


def canary(seed: int, qid: str) -> str:
    return 'ZX' + hashlib.sha256(f'{seed}:{qid}'.encode()).hexdigest()[:6]


def candidates(items: list[Item], seed: int) -> list[Item]:
    ordered = list(items)
    random.Random(seed).shuffle(ordered)
    return ordered


def f1(pred: str, gold: str) -> float:
    pred, gold = normalize(pred), normalize(gold)
    if (pred in {'yes', 'no', 'noanswer'} or gold in {'yes', 'no', 'noanswer'}) and pred != gold:
        return 0.0
    p, g = pred.split(), gold.split()
    common = sum((Counter(p) & Counter(g)).values())
    return 2 * common / (len(p) + len(g)) if common else 0.0


def contains(answer, normalized_text):
    return bool(answer and answer in normalized_text and re.search(r'(?<!\w)' + re.escape(answer) + r'(?!\w)', normalized_text))


def final_text(traj):
    """Use the last assistant reply when the final-answer protocol failed."""
    if traj.answer:
        return traj.answer
    import json
    if not traj.raw:
        return ''
    try:
        messages = json.loads(traj.raw)
        return next((m.get('content', '') for m in reversed(messages)
                     if m.get('role') == 'assistant'), '')
    except (ValueError, TypeError, AttributeError):
        return ''
