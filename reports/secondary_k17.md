# Secondary analyses (k17)

PREREG amendment 2026-11-04. Exploratory unless marked otherwise; no claim from fewer than 30 paired items.

## S1 fused (ReAct) vs decoupled (Plan), c0

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.253 | 0.268 | 15 | 19 | 0.608 | 1.000 |
| citation hallucination ASR | 80 | 0.050 | 0.188 | 1 | 12 | 0.003 | 0.017 |
| unsupported claim ASR | 80 | 0.750 | 0.900 | 3 | 15 | 0.008 | 0.030 |
| counterfactual follow (both exposed) | 15 | 0.067 | 0.267 | 0 | 3 | 0.250 | 0.750 |
| injection ASR | 80 | 0.000 | 0.000 | 0 | 0 | 1.000 | 1.000 |

## S1 fused (ReAct) vs decoupled (Plan), c1

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.257 | 0.261 | 21 | 22 | 1.000 | 1.000 |
| citation hallucination ASR | 80 | 0.075 | 0.275 | 3 | 19 | 0.001 | 0.004 |
| unsupported claim ASR | 80 | 0.900 | 0.900 | 5 | 5 | 1.000 | 1.000 |
| counterfactual follow (both exposed) | 16 | 0.188 | 0.188 | 1 | 1 | 1.000 | 1.000 |
| injection ASR | 80 | 0.000 | 0.013 | 0 | 1 | 1.000 | 1.000 |

## S1 fused (ReAct) vs decoupled (Plan), c2

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.276 | 0.322 | 12 | 24 | 0.065 | 0.196 |
| citation hallucination ASR | 80 | 0.087 | 0.200 | 2 | 11 | 0.022 | 0.112 |
| unsupported claim ASR | 80 | 0.950 | 0.850 | 10 | 2 | 0.039 | 0.154 |
| counterfactual follow (both exposed) | 15 | 0.067 | 0.267 | 0 | 3 | 0.250 | 0.500 |
| injection ASR | 80 | 0.000 | 0.000 | 0 | 0 | 1.000 | 1.000 |

## S3 abstention when evidence is missing (react)

| category | comparison | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|---|
| citation_hallucination | c1 vs c0 | 80 | 0.175 | 0.212 | 6 | 9 | 0.607 | 0.607 |
| citation_hallucination | c2 vs c0 | 80 | 0.100 | 0.212 | 3 | 12 | 0.035 | 0.070 |
| unsupported_claim | c1 vs c0 | 80 | 0.100 | 0.250 | 3 | 15 | 0.008 | 0.023 |
| unsupported_claim | c2 vs c0 | 80 | 0.050 | 0.250 | 0 | 16 | 0.000 | 0.000 |
| clean | c1 vs c0 | 261 | 0.061 | 0.153 | 8 | 32 | 0.000 | 0.001 |
| clean | c2 vs c0 | 261 | 0.042 | 0.153 | 2 | 31 | 0.000 | 0.000 |

## S3 abstention when evidence is missing (plan)

| category | comparison | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|---|
| citation_hallucination | c1 vs c0 | 80 | 0.087 | 0.150 | 0 | 5 | 0.062 | 0.375 |
| citation_hallucination | c2 vs c0 | 80 | 0.113 | 0.150 | 3 | 6 | 0.508 | 1.000 |
| unsupported_claim | c1 vs c0 | 80 | 0.100 | 0.100 | 5 | 5 | 1.000 | 1.000 |
| unsupported_claim | c2 vs c0 | 80 | 0.150 | 0.100 | 7 | 3 | 0.344 | 1.000 |
| clean | c1 vs c0 | 261 | 0.065 | 0.065 | 12 | 12 | 1.000 | 1.000 |
| clean | c2 vs c0 | 261 | 0.061 | 0.065 | 8 | 9 | 1.000 | 1.000 |

## S4 poison dose-response (plan)

Habit: rate on 100 clean questions, paired against the unpoisoned run (a_only = poisoned only). Fact: rate on the k targeted questions, n = k.

| route | kind | k | n | rate | lo | hi | base_rate | paired_n | a_only | b_only | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c1 | fact | 5 | 5 | 0.200 | 0.036 | 0.624 | n/a | n/a | n/a | n/a | n/a |
| c1 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c2 | fact | 5 | 5 | 0.000 | 0.000 | 0.434 | n/a | n/a | n/a | n/a | n/a |
| c2 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
