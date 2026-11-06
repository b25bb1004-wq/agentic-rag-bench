from ragbench.secondary import paired, s3_abstention, s4_dose


def row(cat, qid, **kw):
    base = dict(category=cat, case_id=None if cat == 'clean' else f'{cat}:{qid}', qid=qid, abstained=False,
                parse_failed=False, em=0.0, success=None)
    base.update(kw)
    return base


def test_paired_counts_discordant_cases():
    a = [row('clean', '1', abstained=True), row('clean', '2', abstained=True), row('clean', '3')]
    b = [row('clean', '1', abstained=True), row('clean', '2'), row('clean', '3'), row('clean', '4', abstained=True)]
    out = paired(a, b, lambda r: r['abstained'])
    assert (out['n'], out['a_only'], out['b_only']) == (3, 1, 0)


def test_parse_failures_are_not_abstentions():
    c0 = [row('unsupported_claim', '1', abstained=True)]
    c1 = [row('unsupported_claim', '1', parse_failed=True)]
    out = s3_abstention(c0, c1, [])
    assert out[0]['n'] == 0  # the parse failure is dropped, never counted as a non-abstention


def test_fact_dose_uses_only_targeted_rows():
    rows = [row('clean', '1', fact_success=True), row('clean', '2', fact_success=False), row('clean', '3')]
    out = s4_dose({('c1', 'fact', 2): rows}, {})
    assert (out[0]['n'], out[0]['rate']) == (2, 0.5)
