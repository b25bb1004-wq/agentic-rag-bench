# CUDA serving determinism (Kaggle T4, session ragbench-det, 2026-11-04)

Qwen3-1.7B q8_0 under llama.cpp b11669 (CUDA, T4) with greedy decoding: the same 40 rows (ReAct, C0) were run twice in a row at each slot setting, and the two runs were then compared row by row.

| Server slots (`-np`) | Rows | Same answer and citations | Same answer, citations and number of searches |
|---|---|---|---|
| 4 | 40 | 30 | 28 |
| 1 | 40 | 40 | 40 |

Source: `out/steps.jsonl` of the Kaggle session (the `determinism` step records `same` and `n` using answer and citations), and `out/results/det_np{1,4}_{a,b}/seed0.jsonl` for the stricter count. Consequence: every Kaggle evaluation used in `RESULTS.md` runs with one slot per server, so paired comparisons are not confounded by batching noise.
