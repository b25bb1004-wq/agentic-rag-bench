# Benchmark summary

Valid rows: 4366. Malformed lines skipped: 0.

ASR intervals are Wilson 95% CIs; paired differences use percentile bootstrap (2000 resamples, seed 0). Rates use available, non-null measurements. Supported rate excludes abstentions. Utility is EM on attacked rows with a gold answer.

Clean diagnostic rates use clean rows from the same agent, condition, and inference seeds.

| Agent | Condition | Category | n | EM | F1 | ASR [95% CI] | Clean EM | Clean abstain rate | Clean parse failure rate | Clean unretrieved citation rate | Citation P | Citation R | Supported | Counterfactual sensitivity | Utility under attack | Parse failure rate | Abstain rate | Conditional ASR [95% CI] | Conditional n | Deflected | Unfaithful citation | Edited passage retrieved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plan | c0 | citation_hallucination | 80 | n/a | n/a | 0.1875 [0.1171, 0.2866] | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.0063 | 0.0063 | n/a | n/a | n/a | 0.0000 | 0.1500 | 0.2000 [0.0886, 0.3913] | 25 | n/a | 0.8500 | n/a |
| plan | c0 | clean | 261 | 0.2682 | 0.3645 | n/a | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.4374 | 0.3812 | n/a | n/a | n/a | 0.0000 | 0.0651 | n/a | 0 | n/a | n/a | n/a |
| plan | c0 | counterfactual | 80 | 0.0125 | 0.0467 | 0.2625 [0.1786, 0.3682] | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.3792 | 0.3187 | n/a | 0.0625 | 0.0125 | 0.0000 | 0.0875 | 0.5000 [0.1876, 0.8124] | 6 | n/a | n/a | 0.3375 |
| plan | c0 | injection | 80 | 0.2500 | 0.3636 | 0.0000 [0.0000, 0.0458] | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.4750 | 0.4188 | n/a | n/a | 0.2500 | 0.0000 | 0.1000 | 0.0000 [0.0000, 0.1332] | 25 | 0.1000 | n/a | n/a |
| plan | c0 | jailbreak | 80 | 0.2500 | 0.3215 | 0.1125 [0.0603, 0.2002] | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.4167 | 0.3625 | n/a | n/a | 0.2500 | 0.0000 | 0.1250 | 0.1200 [0.0417, 0.2996] | 25 | n/a | n/a | n/a |
| plan | c0 | unsupported_claim | 80 | n/a | n/a | 0.9000 [0.8149, 0.9485] | 0.2682 | 0.0651 | 0.0000 | 0.1571 | 0.2750 | 0.2125 | n/a | n/a | n/a | 0.0000 | 0.1000 | 0.8750 [0.5291, 0.9776] | 8 | n/a | n/a | n/a |
| plan | c1 | citation_hallucination | 80 | n/a | n/a | 0.2750 [0.1892, 0.3814] | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.0688 | 0.0688 | n/a | n/a | n/a | 0.0000 | 0.0875 | 0.3182 [0.1636, 0.5268] | 22 | n/a | 0.9125 | n/a |
| plan | c1 | clean | 261 | 0.2605 | 0.3609 | n/a | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.5198 | 0.4521 | n/a | n/a | n/a | 0.0000 | 0.0651 | n/a | 0 | n/a | n/a | n/a |
| plan | c1 | counterfactual | 80 | 0.0375 | 0.0525 | 0.2500 [0.1681, 0.3548] | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.4792 | 0.3937 | n/a | 0.0625 | 0.0375 | 0.0000 | 0.0875 | 0.5000 [0.2152, 0.7848] | 8 | n/a | n/a | 0.3125 |
| plan | c1 | injection | 80 | 0.2750 | 0.3664 | 0.0125 [0.0022, 0.0675] | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.5625 | 0.4938 | n/a | n/a | 0.2750 | 0.0000 | 0.0375 | 0.0000 [0.0000, 0.1487] | 22 | 0.0375 | n/a | n/a |
| plan | c1 | jailbreak | 80 | 0.2125 | 0.2988 | 0.0750 [0.0348, 0.1541] | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.5188 | 0.4313 | n/a | n/a | 0.2125 | 0.0000 | 0.0750 | 0.0909 [0.0253, 0.2781] | 22 | n/a | n/a | n/a |
| plan | c1 | unsupported_claim | 80 | n/a | n/a | 0.9000 [0.8149, 0.9485] | 0.2605 | 0.0651 | 0.0000 | 0.1379 | 0.2979 | 0.2375 | n/a | n/a | n/a | 0.0000 | 0.1000 | 0.8889 [0.5650, 0.9801] | 9 | n/a | n/a | n/a |
| plan | c1_poison_fact_k5 | clean | 100 | 0.3800 | 0.4604 | n/a | 0.3800 | 0.0400 | 0.0000 | 0.1200 | 0.5600 | 0.4900 | n/a | n/a | n/a | 0.0000 | 0.0400 | n/a | 0 | n/a | n/a | n/a |
| plan | c1_poison_habit_k5 | clean | 100 | 0.3900 | 0.4695 | n/a | 0.3900 | 0.0400 | 0.0000 | 0.1100 | 0.5650 | 0.4950 | n/a | n/a | n/a | 0.0000 | 0.0400 | n/a | 0 | n/a | n/a | n/a |
| plan | c2 | citation_hallucination | 80 | n/a | n/a | 0.2000 [0.1270, 0.3005] | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.0063 | 0.0063 | n/a | n/a | n/a | 0.0000 | 0.1125 | 0.1875 [0.0889, 0.3531] | 32 | n/a | 0.8875 | n/a |
| plan | c2 | clean | 261 | 0.3218 | 0.4084 | n/a | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.5013 | 0.4138 | n/a | n/a | n/a | 0.0000 | 0.0613 | n/a | 0 | n/a | n/a | n/a |
| plan | c2 | counterfactual | 80 | 0.0500 | 0.0804 | 0.2375 [0.1576, 0.3414] | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.4375 | 0.3563 | n/a | 0.1000 | 0.0500 | 0.0000 | 0.1250 | 0.5000 [0.2152, 0.7848] | 8 | n/a | n/a | 0.3125 |
| plan | c2 | injection | 80 | 0.4000 | 0.5171 | 0.0000 [0.0000, 0.0458] | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.5167 | 0.4625 | n/a | n/a | 0.4000 | 0.0000 | 0.0500 | 0.0000 [0.0000, 0.1072] | 32 | 0.0500 | n/a | n/a |
| plan | c2 | jailbreak | 80 | 0.2750 | 0.3706 | 0.0500 [0.0196, 0.1216] | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.5250 | 0.4250 | n/a | n/a | 0.2750 | 0.0000 | 0.1500 | 0.0625 [0.0173, 0.2015] | 32 | n/a | n/a | n/a |
| plan | c2 | unsupported_claim | 80 | n/a | n/a | 0.8500 [0.7559, 0.9121] | 0.3218 | 0.0613 | 0.0000 | 0.1533 | 0.3312 | 0.2500 | n/a | n/a | n/a | 0.0000 | 0.1500 | 0.9091 [0.6226, 0.9838] | 11 | n/a | n/a | n/a |
| plan | c2_poison_fact_k5 | clean | 100 | 0.3900 | 0.4355 | n/a | 0.3900 | 0.0000 | 0.0000 | 0.0700 | 0.5600 | 0.4700 | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | 0 | n/a | n/a | n/a |
| plan | c2_poison_habit_k5 | clean | 100 | 0.4000 | 0.4623 | n/a | 0.4000 | 0.0000 | 0.0000 | 0.2800 | 0.3867 | 0.3650 | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | 0 | n/a | n/a | n/a |
| react | c0 | citation_hallucination | 80 | n/a | n/a | 0.0500 [0.0196, 0.1216] | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.0000 | 0.0000 | n/a | n/a | n/a | 0.0000 | 0.2125 | 0.0000 [0.0000, 0.1380] | 24 | n/a | 0.7875 | n/a |
| react | c0 | clean | 261 | 0.2529 | 0.3350 | n/a | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.5715 | 0.3372 | n/a | n/a | n/a | 0.0000 | 0.1533 | n/a | 0 | n/a | n/a | n/a |
| react | c0 | counterfactual | 80 | 0.0125 | 0.0137 | 0.2250 [0.1473, 0.3279] | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.5000 | 0.2687 | n/a | 0.0125 | 0.0125 | 0.0000 | 0.2750 | 0.8000 [0.3755, 0.9638] | 5 | n/a | n/a | 0.2500 |
| react | c0 | injection | 80 | 0.2625 | 0.3237 | 0.0000 [0.0000, 0.0458] | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.5771 | 0.3688 | n/a | n/a | 0.2625 | 0.0000 | 0.1500 | 0.0000 [0.0000, 0.1380] | 24 | 0.1500 | n/a | n/a |
| react | c0 | jailbreak | 80 | 0.2250 | 0.3002 | 0.0375 [0.0128, 0.1045] | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.5083 | 0.3312 | n/a | n/a | 0.2250 | 0.0000 | 0.3375 | 0.0417 [0.0074, 0.2024] | 24 | n/a | n/a | n/a |
| react | c0 | unsupported_claim | 80 | n/a | n/a | 0.7500 [0.6452, 0.8319] | 0.2529 | 0.1533 | 0.0000 | 0.0421 | 0.4250 | 0.2188 | n/a | n/a | n/a | 0.0000 | 0.2500 | 0.7500 [0.4093, 0.9285] | 8 | n/a | n/a | n/a |
| react | c1 | citation_hallucination | 80 | n/a | n/a | 0.0750 [0.0348, 0.1541] | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.0250 | 0.0187 | n/a | n/a | n/a | 0.0000 | 0.1750 | 0.0870 [0.0242, 0.2680] | 23 | n/a | 0.8250 | n/a |
| react | c1 | clean | 261 | 0.2567 | 0.3458 | n/a | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.6073 | 0.3506 | n/a | n/a | n/a | 0.0000 | 0.0613 | n/a | 0 | n/a | n/a | n/a |
| react | c1 | counterfactual | 80 | 0.0250 | 0.0339 | 0.2625 [0.1786, 0.3682] | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.4604 | 0.2500 | n/a | 0.0500 | 0.0250 | 0.0000 | 0.0875 | 0.3333 [0.0968, 0.7000] | 6 | n/a | n/a | 0.2250 |
| react | c1 | injection | 80 | 0.2875 | 0.4196 | 0.0000 [0.0000, 0.0458] | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.6292 | 0.3625 | n/a | n/a | 0.2875 | 0.0000 | 0.0625 | 0.0000 [0.0000, 0.1431] | 23 | 0.0625 | n/a | n/a |
| react | c1 | jailbreak | 80 | 0.2625 | 0.3452 | 0.0000 [0.0000, 0.0458] | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.5771 | 0.3688 | n/a | n/a | 0.2625 | 0.0000 | 0.1125 | 0.0000 [0.0000, 0.1431] | 23 | n/a | n/a | n/a |
| react | c1 | unsupported_claim | 80 | n/a | n/a | 0.9000 [0.8149, 0.9485] | 0.2567 | 0.0613 | 0.0000 | 0.0460 | 0.4062 | 0.2125 | n/a | n/a | n/a | 0.0000 | 0.1000 | 0.8571 [0.4869, 0.9743] | 7 | n/a | n/a | n/a |
| react | c2 | citation_hallucination | 80 | n/a | n/a | 0.0875 [0.0430, 0.1698] | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.0187 | 0.0125 | n/a | n/a | n/a | 0.0000 | 0.1000 | 0.0385 [0.0068, 0.1889] | 26 | n/a | 0.9000 | n/a |
| react | c2 | clean | 261 | 0.2759 | 0.3659 | n/a | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.5856 | 0.3391 | n/a | n/a | n/a | 0.0000 | 0.0421 | n/a | 0 | n/a | n/a | n/a |
| react | c2 | counterfactual | 80 | 0.0125 | 0.0133 | 0.2375 [0.1576, 0.3414] | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.4917 | 0.2562 | n/a | 0.0250 | 0.0125 | 0.0000 | 0.0625 | 0.8000 [0.3755, 0.9638] | 5 | n/a | n/a | 0.2125 |
| react | c2 | injection | 80 | 0.2750 | 0.3804 | 0.0000 [0.0000, 0.0458] | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.5312 | 0.3312 | n/a | n/a | 0.2750 | 0.0000 | 0.0125 | 0.0000 [0.0000, 0.1287] | 26 | 0.0125 | n/a | n/a |
| react | c2 | jailbreak | 80 | 0.2250 | 0.2999 | 0.0125 [0.0022, 0.0675] | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.5083 | 0.3312 | n/a | n/a | 0.2250 | 0.0000 | 0.0500 | 0.0000 [0.0000, 0.1287] | 26 | n/a | n/a | n/a |
| react | c2 | unsupported_claim | 80 | n/a | n/a | 0.9500 [0.8784, 0.9804] | 0.2759 | 0.0421 | 0.0000 | 0.0460 | 0.4000 | 0.2062 | n/a | n/a | n/a | 0.0000 | 0.0500 | 1.0000 [0.5655, 1.0000] | 5 | n/a | n/a | n/a |

## Poisoning

| Agent | Condition base (k=0) | Kind | k | Category | Paired n | Difference | CI low | CI high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plan | c1 | fact | 5 | clean | 5 | 0.2000 | 0.0000 | 0.6000 |
| plan | c1 | habit | 5 | clean | 100 | 0.0000 | 0.0000 | 0.0000 |
| plan | c2 | fact | 5 | clean | 5 | 0.0000 | 0.0000 | 0.0000 |
| plan | c2 | habit | 5 | clean | 100 | 0.0000 | 0.0000 | 0.0000 |

## Primary endpoints (ReAct)

Exact McNemar tests pair unique qids within each seed; Holm covers six endpoints per seed and oracle view. Conditional ASR requires correct clean controls and counterfactual exposure.

| Endpoint | Seed | Paired n | b | c | p | Holm p |
| --- | --- | --- | --- | --- | --- | --- |
| Habit k=5 | 0 | 0 | 0 | 0 | n/a | n/a |
| Fact k=5 | 0 | 0 | 0 | 0 | n/a | n/a |
| Counterfactual C2/C0 | 0 | 14 | 0 | 0 | 1.0000 | 1.0000 |
| Counterfactual C1/C0 | 0 | 14 | 1 | 0 | 1.0000 | 1.0000 |
| Clean C1/C0 | 0 | 261 | 18 | 17 | 1.0000 | 1.0000 |
| Clean C2/C0 | 0 | 261 | 12 | 6 | 0.2379 | 1.0000 |
| Habit k=5+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Fact k=5+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Counterfactual C2/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Counterfactual C1/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Clean C1/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Clean C2/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |

## Secondary endpoints (Plan)

Exact McNemar tests pair unique qids within each seed; Holm covers six endpoints per seed and oracle view. Conditional ASR requires correct clean controls and counterfactual exposure.

| Endpoint | Seed | Paired n | b | c | p | Holm p |
| --- | --- | --- | --- | --- | --- | --- |
| Habit k=5 | 0 | 100 | 0 | 0 | 1.0000 | 1.0000 |
| Fact k=5 | 0 | 5 | 1 | 0 | 1.0000 | 1.0000 |
| Counterfactual C2/C0 | 0 | 22 | 2 | 0 | 0.5000 | 1.0000 |
| Counterfactual C1/C0 | 0 | 20 | 0 | 1 | 1.0000 | 1.0000 |
| Clean C1/C0 | 0 | 261 | 19 | 21 | 0.8746 | 1.0000 |
| Clean C2/C0 | 0 | 261 | 24 | 10 | 0.0243 | 0.1458 |
| Habit k=5+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Fact k=5+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Counterfactual C2/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Counterfactual C1/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Clean C1/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
| Clean C2/C0+oracle | 0 | 0 | 0 | 0 | n/a | n/a |
