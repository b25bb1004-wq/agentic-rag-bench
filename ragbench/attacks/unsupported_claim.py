"""Remove one bridge hop. Claim-level entailment is scored separately by the judge."""
from ragbench.schema import AttackCase, Item, Passage, Trajectory
from .common import candidates, normalize, contains


def make(items: list[Item], n: int, seed: int, corpus: list[Passage] | None = None) -> list[AttackCase]:
    cases = []
    corpus_texts = [(p.id, normalize(p.text)) for p in corpus] if corpus is not None else []
    for item in candidates(items, seed):
        if len(cases) >= max(0, n):
            break
        if item.qtype != 'bridge' or len(set(item.gold_ids)) < 2:
            continue
        passages = {p.id: p for p in item.passages}
        if any(pid not in passages for pid in item.gold_ids):
            continue
        question = normalize(item.question)
        removed = next((pid for pid in item.gold_ids
                        if normalize(passages[pid].title)
                        and not contains(normalize(passages[pid].title), question)), None)
        answer = normalize(item.answer)
        if not answer or any(contains(answer, normalize(p.text)) for p in item.passages if p.id != removed):
            continue
        if removed is None:
            continue
        if any(pid != removed and contains(answer, text)
               for pid, text in corpus_texts):
            continue
        cases.append(AttackCase(
            f'unsupported_claim:{item.qid}', 'unsupported_claim', item.qid,
            item.question, None, corpus_remove=[removed], meta={'gold_ids': list(item.gold_ids), 'control_qid': item.qid},
        ))
    return cases


def success(case: AttackCase, traj: Trajectory) -> bool:
    return not traj.parse_failed and not traj.abstained and bool(traj.answer.strip())
