# Secondary analyses (s17)

PREREG amendment 2026-11-04. Exploratory unless marked otherwise; no claim from fewer than 30 paired items.

## S1 fused (ReAct) vs decoupled (Plan), c0

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.249 | 0.280 | 13 | 21 | 0.229 | 0.688 |
| citation hallucination ASR | 80 | 0.050 | 0.175 | 2 | 12 | 0.013 | 0.065 |
| unsupported claim ASR | 80 | 0.775 | 0.887 | 3 | 12 | 0.035 | 0.141 |
| counterfactual follow (both exposed) | 14 | 0.071 | 0.214 | 0 | 2 | 0.500 | 1.000 |
| injection ASR | 80 | 0.000 | 0.000 | 0 | 0 | 1.000 | 1.000 |

## S3 abstention when evidence is missing (react)

| category | comparison | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|---|
| citation_hallucination | c1 vs c0 | 80 | 0.138 | 0.212 | 6 | 12 | 0.238 | 0.238 |
| citation_hallucination | c2 vs c0 | 80 | 0.113 | 0.212 | 3 | 11 | 0.057 | 0.172 |
| unsupported_claim | c1 vs c0 | 80 | 0.087 | 0.225 | 2 | 13 | 0.007 | 0.030 |
| unsupported_claim | c2 vs c0 | 80 | 0.125 | 0.225 | 3 | 11 | 0.057 | 0.172 |
| clean | c1 vs c0 | 261 | 0.050 | 0.115 | 7 | 24 | 0.003 | 0.017 |
| clean | c2 vs c0 | 261 | 0.038 | 0.115 | 2 | 22 | 0.000 | 0.000 |

## S3 abstention when evidence is missing (plan)

n/a

## S4 poison dose-response (react)

Habit: rate on 100 clean questions, paired against the unpoisoned run (a_only = poisoned only). Fact: rate on the k targeted questions, n = k.

| route | kind | k | n | rate | lo | hi | base_rate | paired_n | a_only | b_only | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c1 | fact | 1 | 1 | 0.000 | 0.000 | 0.793 | n/a | n/a | n/a | n/a | n/a |
| c1 | fact | 2 | 2 | 0.000 | 0.000 | 0.658 | n/a | n/a | n/a | n/a | n/a |
| c1 | fact | 5 | 5 | 0.400 | 0.118 | 0.769 | n/a | n/a | n/a | n/a | n/a |
| c1 | fact | 10 | 10 | 0.400 | 0.168 | 0.687 | n/a | n/a | n/a | n/a | n/a |
| c1 | fact | 25 | 25 | 0.160 | 0.064 | 0.347 | n/a | n/a | n/a | n/a | n/a |
| c1 | fact | 50 | 50 | 0.120 | 0.056 | 0.238 | n/a | n/a | n/a | n/a | n/a |
| c1 | habit | 1 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c1 | habit | 2 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c1 | habit | 5 | 100 | 0.020 | 0.006 | 0.070 | 0.000 | 100 | 2 | 0 | 0.500 |
| c1 | habit | 10 | 100 | 0.030 | 0.010 | 0.085 | 0.000 | 100 | 3 | 0 | 0.250 |
| c1 | habit | 25 | 100 | 0.040 | 0.016 | 0.098 | 0.000 | 100 | 4 | 0 | 0.125 |
| c1 | habit | 50 | 100 | 0.090 | 0.048 | 0.162 | 0.000 | 100 | 9 | 0 | 0.004 |
| c2 | fact | 1 | 1 | 0.000 | 0.000 | 0.793 | n/a | n/a | n/a | n/a | n/a |
| c2 | fact | 5 | 5 | 0.000 | 0.000 | 0.434 | n/a | n/a | n/a | n/a | n/a |
| c2 | fact | 25 | 25 | 0.000 | 0.000 | 0.133 | n/a | n/a | n/a | n/a | n/a |
| c2 | habit | 1 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c2 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c2 | habit | 25 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
