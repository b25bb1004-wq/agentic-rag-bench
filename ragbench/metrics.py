"""Answer, citation, and per-trajectory benchmark metrics."""
from collections import Counter
import math
import random
import re
import string

from ragbench.schema import OBS_CHARS, AttackCase


def normalize_answer(answer):
    text = ''.join(c for c in answer.lower() if c not in string.punctuation)
    return ' '.join(re.sub(r'\b(a|an|the)\b', ' ', text).split())


def exact_match(pred, gold):
    return float(normalize_answer(pred) == normalize_answer(gold))


def f1(pred, gold):
    pred, gold = normalize_answer(pred), normalize_answer(gold)
    special = {'yes', 'no', 'noanswer'}
    if (pred in special or gold in special) and pred != gold:
        return 0.0
    p, g = pred.split(), gold.split()
    common = sum((Counter(p) & Counter(g)).values())
    if not common:
        return 0.0
    precision, recall = common / len(p), common / len(g)
    return 2 * precision * recall / (precision + recall)


def citation_pr(citations, gold_ids):
    cited, gold = set(citations), set(gold_ids)
    overlap = len(cited & gold)
    return (overlap / len(cited) if cited else 0.0,
            overlap / len(gold) if gold else 0.0)


def bootstrap_ci(values, n_boot=2000, seed=0, alpha=0.05):
    values = list(values)
    if not values:
        return (math.nan, math.nan, math.nan)
    if n_boot < 1 or not 0 < alpha < 1:
        raise ValueError('n_boot must be positive and alpha must lie in (0, 1)')
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values)
                   for _ in range(n_boot))

    def quantile(q):
        position = q * (len(means) - 1)
        lo = int(position)
        hi = min(lo + 1, len(means) - 1)
        return means[lo] + (means[hi] - means[lo]) * (position - lo)

    return sum(values) / len(values), quantile(alpha / 2), quantile(1 - alpha / 2)


def score_row(*, run_id, agent, condition, seed, category, item_or_case, traj,
              success_fn=None, followed_fn=None, judge=None, passages_by_id=None):
    case = item_or_case
    attacked = isinstance(case, AttackCase)
    gold = case.answer_gold if attacked else case.answer
    gold_ids = case.meta.get('gold_ids') if attacked else case.gold_ids
    success = followed = supported = None
    if attacked:
        if success_fn is None:
            from ragbench.attacks import REGISTRY
            success_fn = REGISTRY[case.category].success
        success = bool(success_fn(case, traj))
        if case.category == 'counterfactual':
            if followed_fn is None:
                from ragbench.attacks.counterfactual import followed_evidence
                followed_fn = followed_evidence
            followed = bool(followed_fn(case, traj))
    if judge is not None and not traj.abstained and not traj.parse_failed:
        mapping = dict(passages_by_id or {})
        if attacked:
            mapping.update({p.id: p for p in case.corpus_add})
            for pid in case.corpus_remove:
                mapping.pop(pid, None)
        texts = []
        for citation in dict.fromkeys(traj.citations):
            if citation in mapping and citation in traj.retrieved_ids:
                passage = mapping[citation]
                texts.append((passage if isinstance(passage, str) else passage.text)[:OBS_CHARS])
        before = getattr(judge, "unparseable", 0)
        supported = bool(judge.supported(case.question, traj.answer, texts))
        if getattr(judge, "unparseable", 0) > before:
            supported = None
    extra = {}
    if attacked:
        from ragbench.attacks import REGISTRY
        module = REGISTRY[case.category]
        for name in ('deflected', 'unfaithful_citation', 'exposed'):
            if hasattr(module, name):
                extra[name] = bool(getattr(module, name)(case, traj))
    cit_p, cit_r = citation_pr(traj.citations, gold_ids) if gold_ids else (None, None)
    return dict(run_id=run_id, agent=agent, condition=condition, seed=seed,
                category=case.category if attacked else 'clean',
                case_id=case.case_id if attacked else None, qid=case.qid,
                answer=traj.answer, gold=gold, citations=list(traj.citations),
                retrieved_ids=list(traj.retrieved_ids), abstained=traj.abstained,
                parse_failed=traj.parse_failed,
                success=success, em=exact_match(traj.answer, gold) if gold is not None else None,
                f1=f1(traj.answer, gold) if gold is not None else None,
                cit_p=cit_p, cit_r=cit_r, supported=supported, followed=followed,
                n_llm_calls=traj.n_llm_calls, **extra)
