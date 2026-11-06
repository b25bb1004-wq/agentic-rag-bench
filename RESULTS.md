# Results

What has been measured so far, with the test behind each number. Setup and definitions are in `SETUP.md`; every decision made before or during the runs is in `PREREG.md`; raw command outputs are in `reports/`.

Status (2026-11-06): Qwen3-1.7B is complete for both agents. Qwen3-8B is complete except C2 with fact poison at k = 5 (both agents), which ran out of Kaggle session time (see the 8B section).

## What we found (Qwen3-1.7B)

1. **Retrieval memory picked up planted episodes; fine-tuned weights did not, at the doses we trained. The direct comparison is not yet significant.** With fabricated episodes added, the memory agent (C1) copied the planted citation habit on 0, 2, 3, 4 and 9 of 100 questions for k = 1, 5, 10, 25 and 50 poisoned episodes; only k = 50 differs from no poison (9 vs 0 discordant, exact McNemar p = 0.004). The fine-tuned agent (C2) showed no poisoning at k = 1, 5 and 25 (habit 0/100 each; planted wrong answer 0/1, 0/5, 0/25, against 0/1, 2/5 and 4/25 for memory). Paired C1 vs C2 on the same questions, the largest gap is 4 vs 0 at k = 25 (p = 0.125, for both habit and wrong answer). C2 was not trained at k = 50, so the one significant dose has no fine-tuned counterpart.
2. **Fused retrieval cited unretrieved passages less often than decoupled retrieval without memory and with retrieval memory; after fine-tuning the gap is not significant.** When all supporting passages are removed, the interleaved ReAct agent cites a passage it never retrieved in 5% of cases, the plan-then-retrieve agent in 19% (C0; 1 vs 12 discordant, Holm-adjusted p = 0.017). With retrieval memory: 7.5% vs 27.5% (p = 0.004). After fine-tuning: 8.7% vs 20.0% (Holm p = 0.112). Clean accuracy is the same for both agents (0.25 vs 0.27). In every one of the 1,983 Plan episodes the model made exactly two calls (plan, then answer), so its optional follow-up searches were never used and the Plan agent is fully decoupled in these runs.
3. **Training on its own successes made the ReAct agent abstain less when evidence was partly missing.** When one hop of the evidence is removed, ReAct abstains 25% of the time with no memory, 10% with retrieval memory (Holm p = 0.023) and 5% after fine-tuning (0 vs 16 discordant, Holm p < 0.001). On clean questions abstention falls from 15% to 4%. The same pattern appeared on a second hardware stack (Mac Metal run, 22.5% to 12.5%). When all supporting passages are removed the drop is smaller and not significant (21% to 17.5% with memory, p = 0.61; to 10% after fine-tuning, Holm p = 0.070). The plan-then-retrieve agent does not show it (10%, 10%, 15%). A plausible reason: the training episodes are, by construction, confident correct answers, so neither memory nor fine-tuning ever shows the agent an abstention.
4. **No pre-registered primary endpoint is significant.** Closest: clean exact match C2 vs C0, 17 vs 8 discordant (p = 0.11, Holm 0.65). The fact-poisoning endpoint at k = 5 can only ever have 5 items (a design flaw we found and disclosed), so it cannot reach significance.
5. **Model families disagreed sharply on claim support, so no claim-support rate is reported.** Three Qwen3 judges (8B with a lenient and a strict prompt, 32B strict; thinking off) called 62 to 73% of a blind set of multi-hop answers supported by their cited passages. A Gemini labeller and a blind Claude adjudicator called 2 to 7% supported and agreed with each other on 43 of 45 items. Qwen judge vs adjudicator kappa was about 0 for all three, below the pre-registered 0.6. No human labels exist for this set, so this shows that the families disagree, not which one is calibrated; either way the pre-registered judge is not validated, and claim support stays out of the results.

## Main table (Qwen3-1.7B, Kaggle T4, deterministic single-slot serving)

Attack success rate per category; in brackets the conditional rate (paired clean question answered correctly; for the counterfactual, the edited passage also retrieved) and its n. 80 attack cases per category, 261 clean rows per run. Conditional n is small because the 1.7B model answers only about a quarter of clean questions; do not read the bracketed rates as precise.

| Agent | Condition | Clean EM | Clean abstain | Injection | Jailbreak | Citation hallucination | Unsupported claim | Counterfactual (ignored edit) | Edited passage retrieved |
|---|---|---|---|---|---|---|---|---|---|
| ReAct | C0 none | 0.25 | 0.15 | 0.00 (0.00, 24) | 0.04 (0.04, 24) | 0.05 (0.00, 24) | 0.75 (0.75, 8) | 0.23 (0.80, 5) | 0.25 |
| ReAct | C1 memory | 0.26 | 0.06 | 0.00 (0.00, 23) | 0.00 (0.00, 23) | 0.07 (0.09, 23) | 0.90 (0.86, 7) | 0.26 (0.33, 6) | 0.23 |
| ReAct | C2 fine-tuned | 0.28 | 0.04 | 0.00 (0.00, 26) | 0.01 (0.00, 26) | 0.09 (0.04, 26) | 0.95 (1.00, 5) | 0.24 (0.80, 5) | 0.21 |
| Plan | C0 none | 0.27 | 0.07 | 0.00 (0.00, 25) | 0.11 (0.12, 25) | 0.19 (0.20, 25) | 0.90 (0.88, 8) | 0.26 (0.50, 6) | 0.34 |
| Plan | C1 memory | 0.26 | 0.07 | 0.01 (0.00, 22) | 0.07 (0.09, 22) | 0.28 (0.32, 22) | 0.90 (0.89, 9) | 0.25 (0.50, 8) | 0.31 |
| Plan | C2 fine-tuned | 0.32 | 0.06 | 0.00 (0.00, 32) | 0.05 (0.06, 32) | 0.20 (0.19, 32) | 0.85 (0.91, 11) | 0.24 (0.50, 8) | 0.31 |

The 1.7B model almost never follows injected instructions, so injection tells us little at this size; the 8B run is there to test whether that changes with capability.

## Qwen3-8B (Kaggle T4, deterministic single-slot serving; sessions s8a, s8b, s8c)

Both agents, C0 / C1 / C2, an oracle-context control (ReAct C0 with the gold passages always in context), poison k = 5, and a retrieval-budget sweep. C2 is trained on the 8B model's own correct episodes, as for 1.7B. Tables: `reports/kaggle_k8_summary.md` (main and endpoints, budget runs excluded) and `reports/secondary_k8.md` (S1 to S4).

**Missing:** C2 with fact poison at k = 5, for both agents. In the last Kaggle session the Plan C2 fact-k5 training hit its time limit after 8,495 s, and the ReAct C2 fact-k5 evaluation stopped after 3 of 100 rows when the session budget ran out. Those 3 rows are kept in `kaggle_out/s8c_partial/` and are not analysed. Every other planned 8B run completed.

### What we found (Qwen3-8B)

1. **No measurable poisoning at k = 5, for memory or fine-tuning, in either agent.** The planted citation habit appeared on 0 of 100 questions in all four poisoned runs (C1 and C2, ReAct and Plan). The planted wrong answer was copied on 1 of 5 targeted questions by ReAct with memory and 0 of 5 by Plan with memory. This matches 1.7B, where memory poisoning only became significant at k = 50; the 8B was run at k = 5 only.
2. **A bigger model still does not follow injected instructions.** Injection success is 0 to 4% and jailbreak 0 to 4% across all conditions, close to the 1.7B rates. So at 8B, in this setup, prompt injection through retrieved passages is not where the risk shows up.
3. **The 1.7B citation finding does not replicate at 8B.** With all supporting passages removed, both agents rarely cite a passage they never retrieved (ReAct 2.5% vs Plan 1.3% at C0, 2.5% vs 6.3% at C1, 3.8% vs 3.8% at C2; none significant). The gap seen at 1.7B (5% vs 19%) looks like a weakness of the small model, not of decoupled retrieval.
4. **Fused retrieval answers more questions correctly at 8B.** Clean exact match is ReAct 0.41 vs Plan 0.35 at C0 (28 vs 13 discordant, p = 0.028, Holm 0.138) and 0.44 vs 0.37 after fine-tuning (32 vs 13, p = 0.007, Holm 0.033). At 8B too, the Plan agent made exactly two calls in all 1,983 rows of C0, C1 and C2, so this compares interleaved retrieval with a single up-front search.
5. **Fine-tuning again cut abstention on clean questions.** ReAct abstains on 8.8% of clean questions with no memory and 3.1% after fine-tuning (4 vs 19 discordant, Holm p = 0.016), the same direction as at 1.7B (15% to 4%). Unlike 1.7B, the drop on questions with one evidence hop removed is not significant at 8B (23.8% to 17.5%, p = 0.23). Memory does not change abstention at 8B. The Plan agent shows no change.
6. **The 8B model stops searching on its own after one or two searches.** With a cap of 1 search, clean exact match is 0.32; with a cap of 2 it is 0.40, and caps of 3 and 4 add nothing (0.40, 0.39). Even when allowed 4 searches, the agent averages 1.39. Attack rates barely move with the budget (for example, unsupported claim 0.82 at 1 search, 0.74 to 0.76 at 2 to 4). For retrieval-stopping methods (Stop-RAG), this means the base agent already stops early, so there is little over-retrieval to cut on HotpotQA at this size.
7. **The 8B often prefers what it already knows over an edited passage.** When the answer-bearing passage is edited to a different entity, the agent still gives the original answer in 34 to 39% of cases, and in 42% when the edited passage is guaranteed to be in context (oracle control). HotpotQA is Wikipedia and likely in pretraining, so this measures how often parametric memory overrides retrieved evidence.
8. **No pre-registered primary endpoint is significant at 8B.** Closest for ReAct: clean exact match C2 vs C0, 23 vs 13 discordant (p = 0.13, Holm 0.80). For Plan, clean exact match C1 vs C0 is 17 vs 5 (p = 0.017, Holm 0.10). The fact-k5 endpoint has no C2 data (see Missing) and only 5 items by design.

### Main table (Qwen3-8B)

Same format as the 1.7B table: attack success rate, then in brackets the conditional rate and its n. 80 attack cases per category, 261 clean rows per run.

| Agent | Condition | Clean EM | Clean abstain | Injection | Jailbreak | Citation hallucination | Unsupported claim | Counterfactual (ignored edit) | Edited passage retrieved |
|---|---|---|---|---|---|---|---|---|---|
| ReAct | C0 none | 0.41 | 0.09 | 0.03 (0.03, 33) | 0.00 (0.00, 33) | 0.03 (0.00, 33) | 0.76 (0.71, 21) | 0.34 (0.25, 16) | 0.40 |
| ReAct | C0 oracle context | 0.59 | 0.02 | 0.01 (0.02, 51) | 0.00 (0.00, 51) | 0.01 (0.00, 51) | 0.72 (0.72, 39) | 0.42 (0.40, 35) | 1.00 |
| ReAct | C1 memory | 0.42 | 0.08 | 0.04 (0.00, 36) | 0.00 (0.00, 36) | 0.03 (0.03, 36) | 0.72 (0.62, 21) | 0.38 (0.33, 15) | 0.44 |
| ReAct | C2 fine-tuned | 0.44 | 0.03 | 0.01 (0.00, 37) | 0.00 (0.00, 37) | 0.04 (0.00, 37) | 0.82 (0.71, 24) | 0.39 (0.32, 19) | 0.59 |
| Plan | C0 none | 0.35 | 0.08 | 0.03 (0.03, 30) | 0.04 (0.03, 30) | 0.01 (0.00, 30) | 0.81 (0.79, 14) | 0.36 (0.45, 11) | 0.30 |
| Plan | C1 memory | 0.39 | 0.07 | 0.00 (0.00, 35) | 0.00 (0.00, 35) | 0.06 (0.06, 35) | 0.81 (0.86, 14) | 0.38 (0.53, 15) | 0.36 |
| Plan | C2 fine-tuned | 0.37 | 0.07 | 0.01 (0.00, 34) | 0.04 (0.09, 34) | 0.04 (0.00, 34) | 0.85 (0.85, 13) | 0.35 (0.40, 10) | 0.31 |

Unsupported-claim success (an answer given although the evidence for one hop was removed) stays at 72 to 85% at 8B, as at 1.7B: both sizes mostly answer from memory rather than abstain.

## How much to trust this

- Greedy decoding, one inference seed; variance is over questions, with paired exact tests. Kaggle (CUDA) serving was made deterministic (40/40 identical rows across repeated runs) by using one slot per server; with four parallel slots only 30/40 were identical, so batched CUDA serving should not be used for paired comparisons (`reports/kaggle_determinism.md`).
- Comparisons never mix hardware: the Mac (Metal) runs and the Kaggle (CUDA) runs are analysed separately; ReAct numbers in finding 1 and 4 are Mac, findings 2 and 3 are Kaggle with a Mac replication for 3.
- One C2 training seed. HotpotQA only, BM25 retrieval, synthetic attacks.
- Several analyses (findings 1 to 3) were added after the first results were seen; they were registered before their own data existed, and are reported as secondary.
