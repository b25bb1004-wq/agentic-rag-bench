"""Secondary analyses S1-S4 named in the PREREG amendment of 2026-11-04. Lead-owned.

  python -m ragbench.secondary --tag mac17 --react results/s17_react_c0 ... (see main)
Each analysis pairs rows by case (category + case id, or qid for clean rows), uses exact McNemar for binary
outcomes with Holm inside the analysis, Wilson intervals for single rates, and prints n next to every cell.
"""
import argparse
import json
import re
from pathlib import Path

from ragbench.analyze import holm, mcnemar, wilson


def load(folder):
    path = Path(folder) / "seed0.jsonl"
    return [json.loads(line) for line in path.open()] if path.exists() else []


def key(row):
    return row["category"], row["case_id"] or row["qid"]


def paired(rows_a, rows_b, value, keep=lambda a, b: True):
    """Pair two runs by case; value(row) -> 0/1 or None. Returns n, b (a only), c (b only), p."""
    index = {key(r): r for r in rows_b}
    pairs = []
    for a in rows_a:
        b = index.get(key(a))
        if b is not None and keep(a, b):
            va, vb = value(a), value(b)
            if va is not None and vb is not None:
                pairs.append((int(va), int(vb)))
    only_a = sum(x == 1 and y == 0 for x, y in pairs)
    only_b = sum(x == 0 and y == 1 for x, y in pairs)
    return dict(n=len(pairs), rate_a=_rate(p[0] for p in pairs), rate_b=_rate(p[1] for p in pairs),
                a_only=only_a, b_only=only_b, p=mcnemar(only_a, only_b) if pairs else None)


def _rate(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def rate(rows, value):
    values = [v for v in (value(r) for r in rows) if v is not None]
    lo, hi = wilson(int(sum(values)), len(values)) if values else (None, None)
    return dict(n=len(values), rate=_rate(values), lo=lo, hi=hi)


def category(rows, name):
    return [r for r in rows if r["category"] == name]


def attack_success(row):
    return None if row.get("success") is None else bool(row["success"])


def abstained(row):
    return None if row.get("parse_failed") else bool(row["abstained"])


def s1_fused_vs_decoupled(react, plan):
    """ReAct (fused) vs Plan (decoupled) on the same cases, one family per condition."""
    tests = [("clean EM", "clean", lambda r: r["em"], lambda a, b: True),
             ("citation hallucination ASR", "citation_hallucination", attack_success, lambda a, b: True),
             ("unsupported claim ASR", "unsupported_claim", attack_success, lambda a, b: True),
             ("counterfactual follow (both exposed)", "counterfactual",
              lambda r: None if r.get("followed") is None else bool(r["followed"]),
              lambda a, b: bool(a.get("exposed")) and bool(b.get("exposed"))),
             ("injection ASR", "injection", attack_success, lambda a, b: True)]
    out = [dict(test=name, **paired(category(react, cat), category(plan, cat), value, keep))
           for name, cat, value, keep in tests]
    for row, p in zip(out, holm([r["p"] if r["p"] is not None else 1.0 for r in out])):
        row["p_holm"] = p
    return out


def s2_budget(runs):
    """runs: {budget: rows}. Attack success and mean searches per category against the search budget."""
    out = []
    for budget, rows in sorted(runs.items()):
        for cat in ("clean", "injection", "jailbreak", "citation_hallucination", "unsupported_claim", "counterfactual"):
            group = category(rows, cat)
            if not group:
                continue
            value = (lambda r: r["em"]) if cat == "clean" else attack_success
            searches = [r.get("n_searches") for r in group if r.get("n_searches") is not None]
            out.append(dict(budget=budget, category=cat, mean_searches=_rate(searches), **rate(group, value)))
    return out


def s3_abstention(c0, c1, c2):
    out = []
    for cat in ("citation_hallucination", "unsupported_claim", "clean"):
        for name, rows in (("c1", c1), ("c2", c2)):
            if rows and c0:
                out.append(dict(category=cat, comparison=f"{name} vs c0",
                                **paired(category(rows, cat), category(c0, cat), abstained)))
    for row, p in zip(out, holm([r["p"] if r["p"] is not None else 1.0 for r in out])):
        row["p_holm"] = p
    return out


def s4_dose(runs, base):
    """runs: {(route, kind, k): rows}; base: {route: unpoisoned rows}. Poison rate per k, paired against k = 0."""
    out = []
    for (route, kind, k), rows in sorted(runs.items()):
        clean = category(rows, "clean")
        if kind == "habit":
            value = lambda r: bool(r.get("habit_success"))
            pair = paired(clean, category(base.get(route, []), "clean"), value)
            single = rate(clean, value)
            result = dict(n=single["n"], rate=single["rate"], lo=single["lo"], hi=single["hi"], base_rate=pair["rate_b"],
                          paired_n=pair["n"], a_only=pair["a_only"], b_only=pair["b_only"], p=pair["p"])
        else:  # fact poison is scored only on the k targeted questions; no unpoisoned pair exists
            targeted = [r for r in clean if "fact_success" in r]
            result = dict(rate(targeted, lambda r: bool(r["fact_success"])), base_rate=None, paired_n=None,
                          a_only=None, b_only=None, p=None)
        out.append(dict(route=route, kind=kind, k=k, **result))
    return out


def table(rows):
    if not rows:
        return "n/a\n"
    headers = list(rows[0])
    fmt = lambda v: "n/a" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
                     + ["| " + " | ".join(fmt(r.get(h)) for h in headers) + " |" for r in rows]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results", help="folder holding run folders")
    ap.add_argument("--prefix", default="s17", help="run-name prefix: s17 (Mac 1.7B), k17 (Kaggle 1.7B), k8 (Kaggle 8B)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root, px = Path(a.root), a.prefix
    run = lambda name: load(root / f"{px}_{name}")
    sections = [f"# Secondary analyses ({px})\n\nPREREG amendment 2026-11-04. Exploratory unless marked otherwise; "
                "no claim from fewer than 30 paired items.\n"]
    for cond in ("c0", "c1", "c2"):
        if run(f"react_{cond}") and run(f"plan_{cond}"):
            sections.append(f"## S1 fused (ReAct) vs decoupled (Plan), {cond}\n\n"
                            + table(s1_fused_vs_decoupled(run(f"react_{cond}"), run(f"plan_{cond}"))))
    budgets = {int(m.group(1)): load(p) for p in root.glob(f"{px}_react_c0_budget*")
               if (m := re.search(r"budget(\d+)$", p.name))}
    if budgets:
        sections.append("## S2 retrieval budget (ReAct C0)\n\n" + table(s2_budget(budgets)))
    for agent in ("react", "plan"):
        if run(f"{agent}_c0"):
            sections.append(f"## S3 abstention when evidence is missing ({agent})\n\n"
                            + table(s3_abstention(run(f"{agent}_c0"), run(f"{agent}_c1"), run(f"{agent}_c2"))))
    for agent in ("react", "plan"):
        runs = {}
        for p in root.glob(f"{px}_{agent}_c[12]_poison_*_k*"):
            m = re.search(r"_(c[12])_poison_(habit|fact)_k(\d+)$", p.name)
            if m:
                runs[m.group(1), m.group(2), int(m.group(3))] = load(p)
        if runs:
            base = {route: run(f"{agent}_{route}") for route in ("c1", "c2")}
            sections.append(f"## S4 poison dose-response ({agent})\n\nHabit: rate on 100 clean questions, paired "
                            "against the unpoisoned run (a_only = poisoned only). Fact: rate on the k targeted "
                            "questions, n = k.\n\n" + table(s4_dose(runs, base)))
    Path(a.out).write_text("\n".join(sections))
    print(f"wrote {a.out} ({len(sections) - 1} sections)")


if __name__ == "__main__":
    main()
