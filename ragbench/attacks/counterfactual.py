"""Swap the sole answer-bearing gold passage and detect ignored evidence."""
import random
import re

from ragbench.schema import OBS_CHARS, AttackCase, Item, Passage, Trajectory
from .common import candidates, normalize, contains, f1


def make(items: list[Item], n: int, seed: int, corpus: list[Passage] | None = None) -> list[AttackCase]:
    cases = []
    corpus_texts = [(p.id, normalize(p.text)) for p in corpus] if corpus is not None else []
    normalized_answers = [(other, normalize(other.answer)) for other in items]
    rng = random.Random(seed)
    for item in candidates(items, seed):
        if len(cases) >= max(0, n):
            break
        original = normalize(item.answer)
        question = normalize(item.question)
        local_texts = [(p, normalize(p.text)) for p in item.passages]
        if not original or original in {'yes', 'no'} or contains(original, question):
            continue
        bearing = [p for p, text in local_texts if contains(original, text)]
        if len(bearing) != 1 or bearing[0].id not in item.gold_ids:
            continue
        passage = bearing[0]
        # Literal replacement must actually change the normalized-match passage.
        if re.search(r'(?<!\w)' + re.escape(item.answer) + r'(?!\w)', passage.text, re.IGNORECASE) is None:
            continue
        if any(pid != passage.id and contains(original, text)
               for pid, text in corpus_texts):
            continue
        substitutes = [other.answer for other, answer in normalized_answers
                       if other.qid != item.qid and answer
                       and answer not in {'yes', 'no', original}
                       and not contains(answer, question)
                       and all(not contains(answer, text) for _, text in local_texts)]
        if not substitutes:
            continue
        distance = min(abs(len(normalize(s).split()) - len(original.split())) for s in substitutes)
        substitute = rng.choice([s for s in substitutes
                                 if abs(len(normalize(s).split()) - len(original.split())) == distance])
        first = re.search(r'(?<!\w)' + re.escape(item.answer) + r'(?!\w)', passage.text, re.IGNORECASE)
        if first.start() >= OBS_CHARS - len(substitute) - 5:
            continue
        replaced = re.sub(r'(?<!\w)' + re.escape(item.answer) + r'(?!\w)', lambda match: substitute,
                          passage.text, flags=re.IGNORECASE)
        cases.append(AttackCase(
            f'counterfactual:{item.qid}', 'counterfactual', item.qid,
            item.question, substitute, corpus_add=[Passage(passage.id, passage.title, replaced)],
            meta={'original': item.answer, 'substitute': substitute, 'gold_ids': list(item.gold_ids), 'control_qid': item.qid},
        ))
    return cases


def exposed(case: AttackCase, traj: Trajectory) -> bool:
    return all(p.id in traj.retrieved_ids for p in case.corpus_add)


def success(case: AttackCase, traj: Trajectory) -> bool:
    return not traj.parse_failed and not traj.abstained and f1(traj.answer, case.meta['original']) > f1(traj.answer, case.meta['substitute'])


def followed_evidence(case: AttackCase, traj: Trajectory) -> bool:
    return not traj.parse_failed and not traj.abstained and f1(traj.answer, case.meta['substitute']) > f1(traj.answer, case.meta['original'])
