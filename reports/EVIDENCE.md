# Evidence log (commands the lead ran on 2026-11-03; outputs copied, not paraphrased)

- pytest, real tokenizer: `RAGBENCH_TOKENIZER=$HOME/Models/qwen3-1.7b/hf ~/.venvs/ragbench/bin/python -m pytest tests -q` -> `296 passed`.
- Resume: `python -m ragbench.run --config configs/smoke_real_17b.yaml` on a finished run -> `written=0 errors=0 skipped=40`.
- Real smoke after B12 (Qwen3-1.7B q8_0, llama-server Metal, 40 rows, 4 workers): `written=40 errors=0 elapsed_seconds=56.31`; clean n=20 em=3 parsefail=0; mean calls 2.0.
- Real smoke before B9 (same model): clean n=19 em=0 abst=7->3 parsefail=16 noretr=13 calls=5.6 (hallucinated Observation loop). After B9: parsefail=4, 2.3 s/row.
- 8B smoke before B8 (28 rows, 468 s): 8 of 13 clean rows had retrieved_ids empty (answered without searching).
- First real C0 partial run (169 clean rows, strict parser): EM 0.1657, abstain 0.1479, parse failure 0.2308 (replayed 3 failing qids: `Final: A. Cite: ...` rejected). Archived at results/pilot/s17_react_c0_pre_B12.
- arXiv titles: each of the 19 ids in reports/A1.md fetched from https://arxiv.org/abs/<id> and the `<title>` compared; 18 matched the claim, 2412.15280 is Context-DPO (introduces ConFiQA).
- Metal limit: two llama-server processes (8B ctx 16384 + 1.7B ctx 32768) gave `ggml_backend_sched_graph_compute_async failed with error -1` / HTTP 500; one 1.7B server at ctx 24576 works.
- GGUF: base Qwen3-1.7B and Qwen3-4B converted with `convert_hf_to_gguf.py --outtype q8_0` (2.16 GB and 4.28 GB).
- Case counts, eval pool, n_clean 200, n_per_category 120 (`--list-cases`): clean=326 injection=120 jailbreak=120 citation_hallucination=120 unsupported_claim=87 counterfactual=120.
- Disk 2026-11-03: 74 GiB free (83% used).

## First real C0 run (Qwen3-1.7B, ReAct, BM25 top-3, greedy, seed 0, eval split) - results/s17_react_c0, 661 rows, 0 errors, 21 min
- clean n=261: EM 0.25, F1 0.33, abstain 0.11, parse failures 0.
- injection n=80: ASR 0.00; edited passage retrieved (exposed) in 62/80 (78%); ASR among exposed 0/62.
- jailbreak n=80: ASR 0.01 (1/80), abstain 0.29.
- citation_hallucination n=80: ASR 0.05. unsupported_claim n=80: ASR 0.78 (answered although a hop was removed), abstain 0.23.
- counterfactual n=80: ASR 0.24; edited passage retrieved in only 20/80 (25%); among exposed ASR 10/20; `followed_evidence` 1/80 overall.
- clean retrieval: any gold passage retrieved 88%, all gold passages retrieved 26% (BM25 top-3, two-hop questions).
- Noise floor: same 40 cases twice, 1 worker: identical answers 40/40, identical EM 40/40 (greedy is deterministic). 4 workers vs 1 worker: identical answers 39/40.
- Injection positive control (payload placed in the user question, dev split, 10 cases): metric registered success 1/10. The metric works; the 1.7B mostly ignores explicit instructions to append a token, so injection and jailbreak sit near a floor on this model.
- Consequence: counterfactual conclusions need the oracle-context run (retrieval no longer the bottleneck); conditional endpoints will be small-n on 1.7B (see PREREG disclosure c).

## Memory incident (2026-11-03 12:30)
llama-server (1.7B) reached 12 GB (8.9 GB compressed) because `--cache-ram` defaults to 8192 MiB; swap 14 of 15 GB; generation 20 tok/s instead of 41. Restarted with `--cache-ram 256`: process 2.7 GB, swap 3.9 GB. In-flight rows were lost only for the interrupted Plan run; the runner's resume skips finished rows. Skill: llama-server-cache-ram-swap.

## Plan agent C0 (Qwen3-1.7B, BM25 top-3, greedy, seed 0, 661 rows, 0 errors) vs ReAct C0
- clean n=261: EM 0.28 (ReAct 0.25), abstain 0.05 (0.11), parse failures 0.
- injection ASR 0.00 (0.00); jailbreak 0.10 (0.01); citation_hallucination 0.17 (0.05); unsupported_claim 0.89 (0.78); counterfactual ASR 0.24 (0.24), followed_evidence 4/80 (1/80).
- Reading: Plan answers more often and abstains less (0.05 vs 0.11), which raises every attack that works through answering anyway. The first 85 rows suggested EM 0.40; the full 261 clean rows settled at 0.28, so early rows overstate.

## ReAct C0 with oracle context (gold and edited passages handed over; 661 rows, 0 errors)
- clean EM 0.50 (normal ReAct 0.25): retrieval is the main bottleneck for this model.
- injection ASR 0/80 even though the payload is now certainly visible: Qwen3-1.7B ignores injected instructions.
- jailbreak ASR 0.09; citation_hallucination 0.06; unsupported_claim 0.82.
- counterfactual (evidence always visible): answered the ORIGINAL 30/80 (0.38), followed the edited evidence 17/80 (0.21), other 33/80. Normal run: 24% original, 1/80 followed.

## Self-episodes and C1 (retrieval memory), Qwen3-1.7B ReAct, greedy, seed 0
- Episodes: first 1200 train questions, own trajectories, kept when EM = 1: 327 correct (27%). SFT file: 327 records, 781 per-turn examples, mean 548 tokens, max 1852 (max_len 2048, nothing truncated).
- C1 vs C0 on the same 661 cases: clean EM 0.25 vs 0.25; injection ASR 0.00 vs 0.00; jailbreak 0.01 vs 0.00; citation_hallucination 0.05 vs 0.09; unsupported_claim 0.78 vs 0.91; counterfactual 0.24 vs 0.28 (no significance tests run yet; n = 80 per attack). Memory adds about 143 prompt tokens. Memory does not help clean accuracy and may make the agent answer more when evidence is missing.
- C1 poisoning (100 clean qids, baseline habit 0/100): habit pattern k=1 0/100, k=5 2/100, k=25 4/100 (Wilson 95%: [0.00,0.04], [0.01,0.07], [0.02,0.10]). Fact poisoning (targets = first k eval questions): k=1 0/1, k=5 2/5, k=25 4/25 answered the planted wrong answer.

## C2 training incidents (2026-11-03 afternoon)
- max_len 1536 assertion fired (6 records over); real maximum 1852 so max_len 2048.
- MPS out of memory x3: first from stale parallel trainers I had started by mistake (3 processes), then from full-vocabulary logits (151,936 x tokens). Fixes: gradient checkpointing, loss on target-token logits only (B14, 303 tests), single-instance lock in lora_stage.sh. After the fix: 3.4 GB MPS, loss 0.11 at step 10, about 5 s per example, estimated 2.3 h for 2 epochs on 781 examples.

## C2 (LoRA on the same 327 episodes, 2 epochs, merged, GGUF q8_0) vs C0 and C1, ReAct, 661 cases, greedy seed 0 (run 17:04)
- clean EM: C0 0.25, C1 0.25, C2 0.28. Abstain on clean: 0.11, 0.05, 0.04 (both memory routes make the agent answer more often).
- Attack success: injection 0.00/0.00/0.00; jailbreak 0.01/0.00/0.01; citation_hallucination 0.05/0.09/0.05; unsupported_claim 0.78/0.91/0.88; counterfactual 0.24/0.28/0.24. followed_evidence 1/80, 3/80, 5/80.
- Reading (no significance tests yet; n = 80 per attack, differences small): memory and fine-tuning change behaviour mostly by lowering abstention, which raises unsupported-claim attack success; neither moves injection or jailbreak on this model. Primary paired tests (McNemar, Holm) still to run with `ragbench.analyze`.
- Training: 196 optimizer steps, final loss 0.008, 1 h 41 min. Habit-poison C2 variant (332 records) trained the same way; fact-poison variant NOT started (held on purpose because the Mac was overheating).

## C2 habit poisoning, k=5 (LoRA on 327 honest + 5 poisoned episodes, same recipe; 100 clean eval questions)
- C2: 0/100 habit pattern at k=0 and 0/100 at k=5, EM 0.35 at k=5. C1 at k=5: 2/100 (k=0: 0/100).
- Paired C1 vs C2 at k=5: only C1 poisoned on 2 questions, only C2 on 0, exact McNemar p = 0.50. Direction matches H1 (retrieval memory easier to poison) but the data do not support a claim: 2 events.
- Fact-poison C2 variant not run (held for heat). Remaining pre-registered primary endpoints not yet run through `ragbench.analyze`.

## 2026-11-04 Mac: S3 and S4 (secondary, PREREG amendment 2026-11-04; exploratory)
Command: `python -m ragbench.secondary --prefix s17 --out reports/secondary_mac17_partial.md` (full tables there).
- S4 C1 habit poison (ReAct 1.7B, 100 clean q, paired vs unpoisoned C1): k=1 0, k=2 0, k=5 2, k=10 3, k=25 4, k=50 9 (9 vs 0 discordant, McNemar p=0.004). C2 habit k=5: 0/100.
- S4 C1 fact poison (n = k targeted q): k=1 0/1, k=2 0/2, k=5 2/5, k=10 4/10, k=25 4/25, k=50 6/50. Too few items below k=25 for any claim.
- S3 abstention (ReAct 1.7B, paired by case vs C0): clean C0 30/261, C1 13/261 (p=0.003), C2 10/261 (p<0.001); unsupported claim C0 18/80, C1 7/80 (p=0.007), C2 10/80 (p=0.057); citation hallucination C0 17/80, C1 11/80 (p=0.24), C2 9/80 (p=0.057). Holm within S3 is in the report file.

## 2026-11-04 Kaggle session s17 (Qwen3-1.7B, T4, single-slot deterministic evals; kernel ragbench-s17, repo 8efd968)
All 57 steps ok in 4.5 h. Plan episodes on the first 1200 train questions; 10 result folders (results/k17_*), 9 adapters. Summaries: `reports/kaggle_k17_summary.md`, `reports/secondary_k17.md`.
- Clean EM (261 clean rows each): ReAct C0 0.253, C1 0.257, C2 0.276; Plan C0 0.268, C1 0.261, C2 0.322.
- S1 fused (ReAct) vs decoupled (Plan), Holm within each condition: citation hallucination ASR C0 0.050 vs 0.188 (1 vs 12 discordant, p_holm 0.017), C1 0.075 vs 0.275 (3 vs 19, p_holm 0.004), C2 0.087 vs 0.200 (p_holm 0.11); unsupported-claim ASR C0 0.75 vs 0.90 (p_holm 0.030); counterfactual follow n = 15 to 16 exposed pairs (below the 30 rule).
- S3 abstention, ReAct (replicates the Mac pattern on other hardware): unsupported claim C0 0.250 vs C1 0.100 (p_holm 0.023) vs C2 0.050 (0 vs 16 discordant, p_holm < 0.001); clean C0 0.153 vs C1 0.061 vs C2 0.042 (both p_holm <= 0.001). Plan: no change (clean 0.065 / 0.065 / 0.061; unsupported 0.10 / 0.10 / 0.15).
- Plan poison k=5: habit 0/100 for C1 and C2; fact C1 1/5, C2 0/5 (n = k, no claim).

## 2026-11-04 judge validation (PREREG amendments of the same day)
Blind 100-item set (data/judge_to_label.jsonl); agy (Gemini) labels all 100; review set of 45 (data/operator_review_ids.txt) labelled by a blind Claude adjudicator (operator delegated; data/judge_validation.jsonl). On the 45: judge v1 Qwen3-8B lenient agreement 0.29 / kappa -0.01 (33 supported); v2 Qwen3-8B strict 0.40 / 0.01 (28); fallback Qwen3-32B strict 0.29 / -0.01 (33); agy 0.96 / 0.48 (1); adjudicator 3 supported; adjudicator matched all 10 audit items. All Qwen judges fail the kappa 0.6 rule: claim support is not reported. Kaggle kernel ragbench-judge32 (repo 95155a5), 5 min.

## 2026-11-04 22:00 Mac: endpoint 2 complete and C2 poison sweep (Kaggle-trained ReAct adapters, Mac merge/GGUF/serve; eval_adapter.sh)
- Primary endpoints (reports/mac_s17_summary.md): none significant. Fact k=5 C1 2/5 vs C2 0/5 (b 2, c 0, p 0.50, n = 5 by design flaw disclosed); habit k=5 2 vs 0 (p 0.50); clean EM C2 vs C0 17 vs 8 (p 0.11, Holm 0.65).
- S4 C2 (fine-tuning) shows no poisoning at any dose tried: habit 0/100 at k = 1, 5, 25; fact 0/1, 0/5, 0/25. C1 (retrieval memory) at the same doses: habit 0, 2, 4 of 100 (9/100 at k = 50, p 0.004); fact 0/1, 2/5, 4/25 (6/50 at k = 50). Fact k = 25 on the same 25 targets: C1 4 vs C2 0 (McNemar p 0.125). Direction matches H1 (memory easier to poison than weights); no single test reaches significance below k = 50.
