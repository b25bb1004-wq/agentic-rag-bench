# Secondary analyses (k8)

PREREG amendment 2026-11-04. Exploratory unless marked otherwise; no claim from fewer than 30 paired items.

## S1 fused (ReAct) vs decoupled (Plan), c0

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.406 | 0.349 | 28 | 13 | 0.028 | 0.138 |
| citation hallucination ASR | 80 | 0.025 | 0.013 | 2 | 1 | 1.000 | 1.000 |
| unsupported claim ASR | 80 | 0.762 | 0.812 | 7 | 11 | 0.481 | 1.000 |
| counterfactual follow (both exposed) | 18 | 0.111 | 0.167 | 0 | 1 | 1.000 | 1.000 |
| injection ASR | 80 | 0.025 | 0.025 | 2 | 2 | 1.000 | 1.000 |

## S1 fused (ReAct) vs decoupled (Plan), c1

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.418 | 0.395 | 21 | 15 | 0.405 | 1.000 |
| citation hallucination ASR | 80 | 0.025 | 0.062 | 0 | 3 | 0.250 | 1.000 |
| unsupported claim ASR | 80 | 0.725 | 0.812 | 6 | 13 | 0.167 | 0.835 |
| counterfactual follow (both exposed) | 20 | 0.250 | 0.300 | 0 | 1 | 1.000 | 1.000 |
| injection ASR | 80 | 0.037 | 0.000 | 3 | 0 | 0.250 | 1.000 |

## S1 fused (ReAct) vs decoupled (Plan), c2

| test | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|
| clean EM | 261 | 0.444 | 0.372 | 32 | 13 | 0.007 | 0.033 |
| citation hallucination ASR | 80 | 0.037 | 0.037 | 1 | 1 | 1.000 | 1.000 |
| unsupported claim ASR | 80 | 0.825 | 0.850 | 5 | 7 | 0.774 | 1.000 |
| counterfactual follow (both exposed) | 20 | 0.250 | 0.300 | 1 | 2 | 1.000 | 1.000 |
| injection ASR | 80 | 0.013 | 0.013 | 0 | 0 | 1.000 | 1.000 |

## S2 retrieval budget (ReAct C0)

| budget | category | mean_searches | n | rate | lo | hi |
|---|---|---|---|---|---|---|
| 1 | clean | 1.000 | 261 | 0.322 | 0.268 | 0.381 |
| 1 | injection | 1.000 | 80 | 0.025 | 0.007 | 0.087 |
| 1 | jailbreak | 1.000 | 80 | 0.000 | 0.000 | 0.046 |
| 1 | citation_hallucination | 1.000 | 80 | 0.037 | 0.013 | 0.105 |
| 1 | unsupported_claim | 1.000 | 80 | 0.825 | 0.727 | 0.893 |
| 1 | counterfactual | 1.000 | 80 | 0.312 | 0.222 | 0.421 |
| 2 | clean | 1.372 | 261 | 0.398 | 0.341 | 0.459 |
| 2 | injection | 1.312 | 80 | 0.025 | 0.007 | 0.087 |
| 2 | jailbreak | 1.137 | 80 | 0.000 | 0.000 | 0.046 |
| 2 | citation_hallucination | 1.337 | 80 | 0.025 | 0.007 | 0.087 |
| 2 | unsupported_claim | 1.375 | 80 | 0.750 | 0.645 | 0.832 |
| 2 | counterfactual | 1.325 | 80 | 0.338 | 0.243 | 0.446 |
| 3 | clean | 1.379 | 261 | 0.395 | 0.337 | 0.455 |
| 3 | injection | 1.337 | 80 | 0.025 | 0.007 | 0.087 |
| 3 | jailbreak | 1.188 | 80 | 0.000 | 0.000 | 0.046 |
| 3 | citation_hallucination | 1.438 | 80 | 0.025 | 0.007 | 0.087 |
| 3 | unsupported_claim | 1.438 | 80 | 0.738 | 0.632 | 0.821 |
| 3 | counterfactual | 1.337 | 80 | 0.325 | 0.232 | 0.434 |
| 4 | clean | 1.387 | 261 | 0.391 | 0.334 | 0.451 |
| 4 | injection | 1.312 | 80 | 0.025 | 0.007 | 0.087 |
| 4 | jailbreak | 1.137 | 80 | 0.000 | 0.000 | 0.046 |
| 4 | citation_hallucination | 1.462 | 80 | 0.025 | 0.007 | 0.087 |
| 4 | unsupported_claim | 1.425 | 80 | 0.762 | 0.659 | 0.842 |
| 4 | counterfactual | 1.337 | 80 | 0.338 | 0.243 | 0.446 |

## S3 abstention when evidence is missing (react)

| category | comparison | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|---|
| citation_hallucination | c1 vs c0 | 80 | 0.237 | 0.312 | 5 | 11 | 0.210 | 1.000 |
| citation_hallucination | c2 vs c0 | 80 | 0.275 | 0.312 | 5 | 8 | 0.581 | 1.000 |
| unsupported_claim | c1 vs c0 | 80 | 0.275 | 0.237 | 11 | 8 | 0.648 | 1.000 |
| unsupported_claim | c2 vs c0 | 80 | 0.175 | 0.237 | 3 | 8 | 0.227 | 1.000 |
| clean | c1 vs c0 | 261 | 0.080 | 0.088 | 12 | 14 | 0.845 | 1.000 |
| clean | c2 vs c0 | 261 | 0.031 | 0.088 | 4 | 19 | 0.003 | 0.016 |

## S3 abstention when evidence is missing (plan)

| category | comparison | n | rate_a | rate_b | a_only | b_only | p | p_holm |
|---|---|---|---|---|---|---|---|---|
| citation_hallucination | c1 vs c0 | 80 | 0.163 | 0.225 | 4 | 9 | 0.267 | 1.000 |
| citation_hallucination | c2 vs c0 | 80 | 0.212 | 0.225 | 4 | 5 | 1.000 | 1.000 |
| unsupported_claim | c1 vs c0 | 80 | 0.188 | 0.188 | 5 | 5 | 1.000 | 1.000 |
| unsupported_claim | c2 vs c0 | 80 | 0.150 | 0.188 | 3 | 6 | 0.508 | 1.000 |
| clean | c1 vs c0 | 261 | 0.073 | 0.077 | 7 | 8 | 1.000 | 1.000 |
| clean | c2 vs c0 | 261 | 0.073 | 0.077 | 5 | 6 | 1.000 | 1.000 |

## S4 poison dose-response (react)

Habit: rate on 100 clean questions, paired against the unpoisoned run (a_only = poisoned only). Fact: rate on the k targeted questions, n = k.

| route | kind | k | n | rate | lo | hi | base_rate | paired_n | a_only | b_only | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c1 | fact | 5 | 5 | 0.200 | 0.036 | 0.624 | n/a | n/a | n/a | n/a | n/a |
| c1 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c2 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |

## S4 poison dose-response (plan)

Habit: rate on 100 clean questions, paired against the unpoisoned run (a_only = poisoned only). Fact: rate on the k targeted questions, n = k.

| route | kind | k | n | rate | lo | hi | base_rate | paired_n | a_only | b_only | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c1 | fact | 5 | 5 | 0.000 | 0.000 | 0.434 | n/a | n/a | n/a | n/a | n/a |
| c1 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
| c2 | habit | 5 | 100 | 0.000 | 0.000 | 0.037 | 0.000 | 100 | 0 | 0 | 1.000 |
