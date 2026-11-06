"""Resumable benchmark execution and a separate passage-grounded judge pass."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import re
import time
import traceback

import yaml

from ragbench.agents.plan import PlanAgent
from ragbench.agents.react import ReActAgent
from ragbench.attacks import REGISTRY
from ragbench.data import build_corpus, load_items, read_splits
from ragbench.judge import Judge
from ragbench.llm import LLM, MockLLM
from ragbench.memory import Episode, RetrievalMemory
from ragbench.metrics import score_row
from ragbench.poison import make_poison_episodes
from ragbench.retriever import HybridRetriever, Overlay
from ragbench.schema import OBS_CHARS, AttackCase, Step, Trajectory


CONDITION = re.compile(r'c[012]|c[12]_poison_(habit|fact)_k([1-9][0-9]*)')


def validate_config(config):
    if config.get('agent') not in {'react', 'plan'}:
        raise ValueError('agent must be react or plan')
    if not CONDITION.fullmatch(config.get('condition', '')):
        raise ValueError('invalid condition')
    if not isinstance(config.get('agent_kwargs') or {}, dict):
        raise ValueError('agent_kwargs must be a mapping')
    if not isinstance(config.get('oracle_context', False), bool):
        raise ValueError('oracle_context must be boolean')
    for key in ('n_clean', 'n_per_category'):
        if not isinstance(config.get(key), int) or config[key] < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    if not isinstance(config.get('name'), str) or not config['name']:
        raise ValueError('name must be nonempty')
    seeds = config.get('seeds', [0, 1, 2])
    if not isinstance(seeds, list) or not all(isinstance(s, int) for s in seeds):
        raise ValueError('seeds must be a list of integers')
    if len(set(seeds)) != len(seeds):
        raise ValueError('seeds must be unique')
    if not isinstance(config.get('workers', 4), int) or config.get('workers', 4) < 1:
        raise ValueError('workers must be positive')


def case_key(case):
    return (case.category, case.case_id) if isinstance(case, AttackCase) else ('clean', case.qid)


def row_key(row):
    # B4 deliberately leaves clean case_id null, so qid identifies its control.
    return row['seed'], row['category'], row['case_id'] if row['category'] != 'clean' else row['qid']


def build_cases(pool, config, seed, limit=None, corpus=None):
    """Limit total rows per seed, admitting an attack and its control together."""
    if limit is not None and limit < 0:
        raise ValueError('limit must be nonnegative')
    by_qid = {item.qid: item for item in pool}
    cases = list(pool[:config['n_clean']])
    if limit is not None:
        cases = cases[:limit]
    controls = {item.qid for item in cases}
    for module in REGISTRY.values():
        kwargs = {'corpus': corpus} if module.__name__.rsplit('.', 1)[-1] in {'counterfactual', 'unsupported_claim'} else {}
        for attack in module.make(pool, config['n_per_category'], seed, **kwargs):
            assert attack.meta['control_qid'] == attack.qid
            control_qid = attack.meta['control_qid']
            control = by_qid[control_qid]
            needed = 1 + (control_qid not in controls)
            if limit is not None and len(cases) + needed > limit:
                continue
            if control_qid not in controls:
                cases.append(control)
                controls.add(control_qid)
            cases.append(attack)
    return cases


def load_episodes(path):
    """Read JSONL of dataclasses.asdict(Episode), including nested steps."""
    episodes = []
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            trajectory = dict(record['trajectory'])
            trajectory['steps'] = [Step(**step) for step in trajectory['steps']]
            episodes.append(Episode(record['qid'], record['question'],
                                    Trajectory(**trajectory), record['correct']))
    return episodes


def make_memory(config, pool, seed):
    condition = config['condition']
    if not condition.startswith('c1'):
        return None
    settings = config.get('memory') or {}
    episodes = load_episodes(settings.get('episodes_path', 'data/episodes.jsonl'))
    match = CONDITION.fullmatch(condition)
    if match.group(1):
        episodes += make_poison_episodes(match.group(1), int(match.group(2)), seed, targets=pool, agent=config['agent'])
    return RetrievalMemory(episodes, k=settings.get('k', 3))


def mock_llm(agent):
    # The callable mock derives each reply from its own conversation.
    def reply(messages):
        if any(m['role'] == 'assistant' for m in messages):
            observations = '\n'.join(m['content'] for m in messages if m['role'] == 'user')
            ids = re.findall(r'\[(p:[^\]\n]+)\]', observations)
            return f'Final: mock answer | Cite: {ids[0]}' if ids else 'Final: UNKNOWN | Cite:'
        question = messages[1]['content'].split('\n')[0]
        return f'Q: {question}' if agent == 'plan' else f'Action: search[{question}]'
    return MockLLM(reply)


def make_llm(config, mock=False):
    if not mock and config.get('llm', {}).get('base_url', '') is None:
        raise ValueError('llm.base_url is null: configure the poisoned model endpoint before running')
    return mock_llm(config['agent']) if mock else LLM(**config.get('llm', {}))


def read_rows(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as source:
        return [json.loads(line) for line in source if line.strip()]


def append_json(handle, record):
    handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    handle.flush()


def execute_case(config, seed, case, retriever, memory, mock, item=None, poison_answers=None, llm=None):
    overlay = Overlay(case.corpus_add, set(case.corpus_remove)) if isinstance(case, AttackCase) else Overlay()
    kwargs = config.get('agent_kwargs') or {}  # e.g. {max_searches: 2} for the retrieval-budget sweep
    agent = ReActAgent(**kwargs) if config['agent'] == 'react' else PlanAgent(**kwargs)
    memory_block, memory_tokens = memory.retrieve_with_size(case.question) if memory else ('', 0)
    prefetch = None
    if config.get('oracle_context', False):
        source = item if isinstance(case, AttackCase) else case
        if source is None:
            raise ValueError('oracle_context requires the original item for attack cases')
        passages = {p.id: p for p in source.passages}
        passages.update({p.id: p for p in overlay.add})
        prefetch = [passages[pid] for pid in source.gold_ids
                    if pid in passages and pid not in overlay.remove]
    traj = agent.run(case.question, retriever, llm if llm is not None else make_llm(config, mock),
                     memory_block=memory_block,
                     system_extra=case.system_extra if isinstance(case, AttackCase) else '',
                     overlay=overlay, seed=seed, prefetch=prefetch)
    traj.qid = case.qid
    condition = config['condition'] + ('+oracle' if config.get('oracle_context', False) else '')
    row = score_row(run_id=config['name'], agent=config['agent'], condition=condition,
                     seed=seed, category=case_key(case)[0], item_or_case=case, traj=traj)
    # Compute from this call's block; memory is shared by concurrent workers.
    row['prompt_tokens_added'] = memory_tokens
    row['n_searches'] = sum(step.kind == 'search' for step in traj.steps)
    from ragbench.poison import habit_success, habit_pattern_success, fact_success
    row['habit_success'] = habit_success(traj)
    row['habit_pattern_success'] = habit_pattern_success(traj)
    if poison_answers is not None and case.qid in poison_answers:
        source = item if isinstance(case, AttackCase) else case
        row['fact_substitute'] = poison_answers[case.qid]
        row['fact_success'] = (not traj.parse_failed and fact_success(source, poison_answers[case.qid], traj))
    return row


def judge_rows(config, seed, cases, corpus, out_dir, mock):
    lookup = {case_key(case): case for case in cases}
    base = {p.id: p for p in corpus}
    judge = Judge(MockLLM(['SUPPORTED']) if mock else LLM(**(config.get('judge_llm') or config.get('llm', {}))))
    destination = out_dir / f'seed{seed}.judged.jsonl'
    temporary = destination.with_suffix('.jsonl.tmp')
    errors = written = 0
    with temporary.open('w', encoding='utf-8') as output, (out_dir / 'errors.jsonl').open('a', encoding='utf-8') as log:
        for row in read_rows(out_dir / f'seed{seed}.jsonl'):
            try:
                case = lookup[row_key(row)[1:]]
                passages = base.copy()
                if isinstance(case, AttackCase):
                    passages.update({p.id: p for p in case.corpus_add})
                    for pid in case.corpus_remove:
                        passages.pop(pid, None)
                before = judge.unparseable
                row['supported'] = None if row['abstained'] or row.get('parse_failed', False) else bool(judge.supported(
                    case.question, row['answer'],
                    [passages[pid].text[:OBS_CHARS] for pid in dict.fromkeys(row['citations'])
                     if pid in passages and pid in row['retrieved_ids']]))
                if judge.unparseable > before:
                    row['supported'] = None
                append_json(output, row)
                written += 1
                if written % 25 == 0:
                    print(f'judge seed={seed} rows={written}', flush=True)
            except Exception as exc:
                errors += 1
                append_json(log, dict(phase='judge', seed=seed, category=row.get('category'),
                                     case_id=row.get('case_id'), qid=row.get('qid'),
                                     error=str(exc), traceback=traceback.format_exc()))
    temporary.replace(destination)
    return written, errors


def run(config, *, mock=False, limit=None, list_cases=False, score_judge=False):
    validate_config(config)
    llm = make_llm(config, mock) if not score_judge and not list_cases else None
    start = time.monotonic()
    items = load_items()
    by_qid = {item.qid: item for item in items}
    pool = [by_qid[qid] for qid in read_splits()[config.get('split', 'eval')]]
    corpus = build_corpus(items)
    seeds = config.get('seeds', [0, 1, 2])
    if list_cases:
        for seed in seeds:
            counts = Counter(case_key(case)[0] for case in build_cases(pool, config, seed, limit, corpus=corpus))
            print(f'seed={seed} ' + ' '.join(f'{category}={counts[category]}' for category in ('clean', *REGISTRY)))
        return {'written': 0, 'errors': 0}
    out_dir = Path(config.get('out_dir', f"results/{config['name']}"))
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieval_settings = dict(config.get('retriever') or {})
    if mock:
        retrieval_settings['dense_model'] = None
    retriever = None if score_judge else HybridRetriever(corpus, **retrieval_settings)
    written = errors = skipped = completed = 0
    for seed in seeds:
        if score_judge:
            # Raw files may contain rows from an earlier run with a larger limit.
            count, failed = judge_rows(config, seed, build_cases(pool, config, seed, corpus=corpus), corpus, out_dir, mock)
            written += count
            errors += failed
            continue
        cases = build_cases(pool, config, seed, limit, corpus=corpus)
        path = out_dir / f'seed{seed}.jsonl'
        expected_condition = config['condition'] + ('+oracle' if config.get('oracle_context', False) else '')
        previous = read_rows(path)
        if any(row['condition'] != expected_condition for row in previous):
            raise ValueError('output contains a different condition; choose a separate out_dir')
        existing = {row_key(row) for row in previous}
        pending = [case for case in cases if (seed, *case_key(case)) not in existing]
        skipped += len(cases) - len(pending)
        if not pending:
            continue
        memory = make_memory(config, pool, seed)
        poison_answers = None
        match = CONDITION.fullmatch(config['condition'])
        if match.group(1) == 'fact':
            poison_answers = {ep.qid: ep.trajectory.answer for ep in make_poison_episodes(
                'fact', int(match.group(2)), seed, targets=pool)}
        with path.open('a', encoding='utf-8') as output, (out_dir / 'errors.jsonl').open('a', encoding='utf-8') as log:
            with ThreadPoolExecutor(max_workers=config.get('workers', 4)) as executor:
                futures = {executor.submit(execute_case, config, seed, case, retriever, memory, mock, by_qid[case.qid], poison_answers, llm): case
                           for case in pending}
                for future in as_completed(futures):
                    case = futures[future]
                    try:
                        append_json(output, future.result())
                        written += 1
                    except Exception as exc:
                        errors += 1
                        append_json(log, dict(phase='run', seed=seed, category=case_key(case)[0],
                                             case_id=case.case_id if isinstance(case, AttackCase) else None,
                                             qid=case.qid, error=str(exc), traceback=traceback.format_exc()))
                    completed += 1
                    if completed % 25 == 0:
                        print(f'cases={completed} written={written} errors={errors}', flush=True)
    print(f'written={written} errors={errors} skipped={skipped} elapsed_seconds={time.monotonic() - start:.2f}', flush=True)
    return dict(written=written, errors=errors, skipped=skipped)


def emit_poison_configs(directory='configs'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for agent in ('react', 'plan'):
        for condition in ('c1', 'c2'):
            source = directory / f'{agent}_{condition}.yaml'
            base = yaml.safe_load(source.read_text(encoding='utf-8'))
            for kind in ('habit', 'fact'):
                for k in (1, 5, 25):
                    config = copy.deepcopy(base)
                    config['condition'] = f'{condition}_poison_{kind}_k{k}'
                    config['name'] = f"{agent}_{config['condition']}"
                    config['out_dir'] = f"results/{config['name']}"
                    comment = ''
                    if condition == 'c2':
                        config['llm'] = {'base_url': None, 'model': None}
                        comment = '# Configure the merged poisoned model endpoint before running.\n'
                    (directory / f"{config['name']}.yaml").write_text(comment + yaml.safe_dump(config, sort_keys=False), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--limit', type=int, help='maximum total rows per seed, including paired controls')
    parser.add_argument('--score-judge', action='store_true')
    parser.add_argument('--list-cases', action='store_true')
    parser.add_argument('--emit-poison-configs', action='store_true')
    args = parser.parse_args(argv)
    if args.emit_poison_configs:
        emit_poison_configs()
        return
    if not args.config:
        parser.error('--config is required unless --emit-poison-configs is used')
    if args.limit is not None and args.limit < 0:
        parser.error('--limit must be nonnegative')
    if args.list_cases and args.score_judge:
        parser.error('--list-cases and --score-judge are mutually exclusive')
    config = yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
    run(config, mock=args.mock, limit=args.limit, list_cases=args.list_cases, score_judge=args.score_judge)


if __name__ == '__main__':
    main()
