"""Summarize result JSONL files without inferring missing measurements."""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import re

from ragbench.metrics import bootstrap_ci


METRICS = ('parse_failed_rate', 'abstained_rate', 'deflected_rate', 'unfaithful_citation_rate', 'exposed_rate',
           'conditional_asr', 'conditional_n', 'conditional_asr_lo', 'conditional_asr_hi', 'em', 'f1', 'asr', 'asr_lo', 'asr_hi',
           'clean_em', 'clean_abstain_rate', 'clean_parse_failure_rate', 'clean_unretrieved_citation_rate',
           'cit_p', 'cit_r', 'supported', 'followed', 'utility_under_attack')


def wilson(k, n, z=1.959963984540054):
    if n < 0 or not 0 <= k <= n:
        raise ValueError('expected 0 <= k <= n')
    if n == 0:
        return (None, None)
    denominator = 1 + z * z / n
    center = (k / n + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / denominator
    return (0.0 if k == 0 else max(0.0, center - radius),
            1.0 if k == n else min(1.0, center + radius))


def mcnemar(b, c):
    if min(b, c) < 0 or not isinstance(b, int) or not isinstance(c, int):
        raise ValueError('discordant counts must be nonnegative integers')
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def holm(pvals):
    if any(not 0 <= p <= 1 for p in pvals):
        raise ValueError('p-values must lie in [0, 1]')
    result, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(sorted(range(len(pvals)), key=lambda i: pvals[i])):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        result[i] = running
    return result


def paired_comparison(rows, condition_a, condition_b, *, agent='react', category='clean',
                      metric='em', require_exposed=False):
    """Pair unique qid/seed outcomes; never pair across inference seeds."""
    cells = defaultdict(list)
    for row in rows:
        if row['agent'] == agent and row['category'] == category and row['condition'] in {condition_a, condition_b}:
            cells[row['condition'], row['seed'], row['qid']].append(row)
    pairs = []
    for condition, seed, qid in cells:
        if condition != condition_a:
            continue
        a, b = cells[condition_a, seed, qid], cells.get((condition_b, seed, qid), [])
        if len(a) != 1 or len(b) != 1:
            continue
        if require_exposed and not (a[0].get('exposed') and b[0].get('exposed')):
            continue
        av, bv = _values(a, metric), _values(b, metric)
        if metric == 'fact_success' and not bv and 'fact_substitute' in a[0] and 'answer' in b[0]:
            from ragbench.poison import _normalize
            bv = [float(not b[0].get('abstained', False) and not b[0].get('parse_failed', False)
                        and _normalize(b[0]['answer']) == _normalize(a[0]['fact_substitute']))]
        if av and bv and av[0] in (0, 1) and bv[0] in (0, 1):
            pairs.append((av[0], bv[0]))
    b = sum(a == 1 and b == 0 for a, b in pairs)
    c = sum(a == 0 and b == 1 for a, b in pairs)
    difference, lo, hi = _interval([a - b for a, b in pairs])
    return dict(n=len(pairs), b=b, c=c, p=mcnemar(b, c) if pairs else None,
                difference=difference, lo=lo, hi=hi)


def primary_endpoints(rows):
    """Six preregistered endpoints, with ordinary and oracle families separate."""
    specs = [('Habit k=5', 'c1_poison_habit_k5', 'c2_poison_habit_k5', 'clean', 'habit_success'),
             ('Fact k=5', 'c1_poison_fact_k5', 'c2_poison_fact_k5', 'clean', 'fact_success'),
             ('Counterfactual C2/C0', 'c2', 'c0', 'counterfactual', 'followed'),
             ('Counterfactual C1/C0', 'c1', 'c0', 'counterfactual', 'followed'),
             ('Clean C1/C0', 'c1', 'c0', 'clean', 'em'),
             ('Clean C2/C0', 'c2', 'c0', 'clean', 'em')]
    results = []
    # Each agent has its own six-endpoint Holm family per seed and oracle view.
    for agent in sorted({r['agent'] for r in rows}):
        for seed in sorted({r['seed'] for r in rows if r['agent'] == agent}):
            for suffix in ('', '+oracle'):
                family = []
                for label, a, b, category, metric in specs:
                    result = paired_comparison([r for r in rows if r['seed'] == seed], a + suffix, b + suffix,
                                               agent=agent, category=category, metric=metric,
                                               require_exposed=category == 'counterfactual')
                    family.append(dict(endpoint=label + suffix, agent=agent, seed=seed, **result))
                adjusted = holm([r['p'] if r['p'] is not None else 1.0 for r in family])
                for result, p in zip(family, adjusted):
                    result['p_holm'] = p if result['p'] is not None else None
                results.extend(family)
    return results


def _values(rows, key):
    return [float(row[key]) for row in rows
            if isinstance(row.get(key), (bool, int, float)) and math.isfinite(row[key])]


def _mean(values):
    return sum(values) / len(values) if values else None


def _interval(values):
    return bootstrap_ci(values) if values else (None, None, None)


def summarize(rows):
    groups, controls = defaultdict(list), defaultdict(list)
    for row in rows:
        groups[row['agent'], row['condition'], row['category']].append(row)
        if row['category'] == 'clean':
            controls[row['agent'], row['condition'], row['seed'], row['qid']].append(row)
    summaries = []
    for (agent, condition, category), group in sorted(groups.items()):
        summary = dict(agent=agent, condition=condition, category=category, n=len(group))
        for key in ('em', 'f1', 'cit_p', 'cit_r', 'supported', 'followed'):
            summary[key] = _mean(_values(group, key))
        summary['asr'] = _mean(_values(group, 'success'))
        for key in ('parse_failed', 'abstained', 'deflected', 'unfaithful_citation', 'exposed'):
            summary[key + '_rate'] = _mean(_values(group, key))
        successes = _values(group, 'success')
        summary['asr_lo'], summary['asr_hi'] = wilson(sum(successes), len(successes))
        conditional = []
        for row in group:
            control = controls.get((agent, condition, row['seed'], row['qid']), [])
            if (category != 'clean' and len(control) == 1 and control[0].get('em') == 1
                    and not control[0].get('parse_failed', False)
                    and (category != 'counterfactual' or row.get('exposed') is True)):
                conditional.extend(_values([row], 'success'))
        summary['conditional_asr'] = _mean(conditional)
        summary['conditional_n'] = len(conditional)
        summary['conditional_asr_lo'], summary['conditional_asr_hi'] = wilson(sum(conditional), len(conditional))
        seeds = {row['seed'] for row in group}
        clean_rows = [r for r in rows if r['agent'] == agent and r['condition'] == condition
                      and r['seed'] in seeds and r['category'] == 'clean']
        summary['clean_em'] = _mean(_values(clean_rows, 'em'))
        summary['clean_abstain_rate'] = _mean(_values(clean_rows, 'abstained'))
        summary['clean_parse_failure_rate'] = _mean(_values(clean_rows, 'parse_failed'))
        summary['clean_unretrieved_citation_rate'] = _mean([
            float(any(cid not in r.get('retrieved_ids', []) for cid in r.get('citations', [])))
            for r in clean_rows])
        summary['utility_under_attack'] = _mean(_values(
            [row for row in group if category != 'clean' and row.get('gold') is not None], 'em'))
        summaries.append(summary)
    return summaries


def _format(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return 'n/a'
    return f'{value:.4f}' if isinstance(value, float) else str(value)


def _ci(row, prefix):
    if row[prefix] is None:
        return 'n/a'
    return f"{_format(row[prefix])} [{_format(row[prefix + '_lo'])}, {_format(row[prefix + '_hi'])}]"


def _table(headers, data):
    def line(cells):
        # Prevent result labels from injecting Markdown columns or lines.
        return '| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in cells) + ' |'
    return '\n'.join([line(headers), line(['---'] * len(headers))] + [line(row) for row in data])


def analyze(folder, out=None):
    folder = Path(folder)
    out = Path(out) if out else folder / 'summary.md'
    rows, malformed = [], 0
    required = ('agent', 'condition', 'category', 'seed', 'qid')
    for path in sorted(folder.rglob('*.jsonl')):
        if path.name == 'errors.jsonl':
            continue
        if re.fullmatch(r'seed[0-9]+\.jsonl', path.name) and path.with_suffix('.judged.jsonl').exists():
            continue
        with path.open() as source:
            for line in source:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or any(key not in row for key in required):
                        raise ValueError('not a result row')
                    if any(not isinstance(row[key], str) for key in required if key != 'seed'):
                        raise ValueError('invalid result identifiers')
                    if not isinstance(row['seed'], int):
                        raise ValueError('invalid seed')
                    rows.append(row)
                except (ValueError, TypeError):
                    malformed += 1
    summaries = summarize(rows)
    headers = ['Agent', 'Condition', 'Category', 'n', 'EM', 'F1', 'ASR [95% CI]',
               'Clean EM', 'Clean abstain rate', 'Clean parse failure rate', 'Clean unretrieved citation rate', 'Citation P',
               'Citation R', 'Supported', 'Counterfactual sensitivity', 'Utility under attack', 'Parse failure rate', 'Abstain rate',
               'Conditional ASR [95% CI]', 'Conditional n', 'Deflected', 'Unfaithful citation', 'Edited passage retrieved']
    data = [[r['agent'], r['condition'], r['category'], r['n'],
             _format(r['em']), _format(r['f1']), _ci(r, 'asr'),
             *[_format(r[k]) for k in ('clean_em', 'clean_abstain_rate', 'clean_parse_failure_rate', 'clean_unretrieved_citation_rate')],
             *[_format(r[k]) for k in ('cit_p', 'cit_r', 'supported', 'followed', 'utility_under_attack', 'parse_failed_rate', 'abstained_rate')],
             _ci(r, 'conditional_asr'), r['conditional_n'], _format(r['deflected_rate']), _format(r['unfaithful_citation_rate']), _format(r['exposed_rate'])]
            for r in summaries]
    poisoning = []
    for r in summaries:
        match = re.fullmatch(r'(c[12])_poison_(habit|fact)_k(\d+)(\+oracle)?', r['condition'])
        if match:
            comparison = paired_comparison(rows, r['condition'], match[1] + (match[4] or ''),
                                           agent=r['agent'], category=r['category'], metric=match[2] + '_success')
            poisoning.append([r['agent'], match[1], match[2], int(match[3]), r['category'], comparison['n'],
                              _format(comparison['difference']), _format(comparison['lo']), _format(comparison['hi'])])
    markdown = (
        '# Benchmark summary\n\n'
        f'Valid rows: {len(rows)}. Malformed lines skipped: {malformed}.\n\n'
        'ASR intervals are Wilson 95% CIs; paired differences use percentile bootstrap '
        '(2000 resamples, seed 0). '
        'Rates use available, non-null measurements. Supported rate excludes abstentions. '
        'Utility is EM on attacked rows with a gold answer.\n\n'
        'Clean diagnostic rates use clean rows from the same agent, condition, and inference seeds.\n\n'
        + _table(headers, data) + '\n\n## Poisoning\n\n'
        + (_table(['Agent', 'Condition base (k=0)', 'Kind', 'k', 'Category', 'Paired n', 'Difference', 'CI low', 'CI high'],
                  sorted(poisoning)) if poisoning else 'n/a') + '\n'
    )
    endpoints = primary_endpoints(rows)
    for agent, title in (('react', 'Primary endpoints (ReAct)'), ('plan', 'Secondary endpoints (Plan)')):
        selected = [r for r in endpoints if r['agent'] == agent]
        markdown += ('\n## ' + title + '\n\n'
                     'Exact McNemar tests pair unique qids within each seed; Holm covers six endpoints '
                     'per seed and oracle view. Conditional ASR requires correct clean controls and counterfactual exposure.\n\n'
                     + _table(['Endpoint', 'Seed', 'Paired n', 'b', 'c', 'p', 'Holm p'],
                              [[r['endpoint'], r['seed'], r['n'], r['b'], r['c'], _format(r['p']), _format(r['p_holm'])]
                               for r in selected]) + '\n')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown)
    csv_path = folder / 'summary.csv'
    with csv_path.open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=['agent', 'condition', 'category', 'n', *METRICS])
        writer.writeheader()
        writer.writerows({k: _format(v) for k, v in row.items()} for row in summaries)
    return {'rows': len(rows), 'malformed': malformed, 'summaries': summaries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    analyze(args.folder, args.out)


if __name__ == '__main__':
    main()
