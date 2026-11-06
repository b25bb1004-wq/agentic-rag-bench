# agentic-rag-bench

A benchmark for one question: when an agent that answers questions from retrieved documents learns from its own past work, is it safer to keep that experience in an external memory it looks up, or to fine-tune it into the model's weights?

Status on 2026-11-06: Qwen3-1.7B and Qwen3-8B are complete for both agents (results in `RESULTS.md`; one 8B condition, fine-tuning with fact poisoning, ran out of compute time and is marked missing). `SETUP.md` explains how to run it and plug in your own agent, retriever, memory or retrieval-stopping policy. `PREREG.md` lists what was decided before each run, including every change made along the way.

## The setup in plain words

- **Task:** multi-hop questions from HotpotQA (the validation set, with every paragraph pooled into one searchable corpus of about 66,000 passages).
- **Agent:** small open models (Qwen3-1.7B and Qwen3-8B) that search the corpus and gives a short answer with citations. Two agent styles: ReAct (search, think, repeat) and Plan-then-retrieve (split the question first).
- **Three conditions:** C0 has no memory. C1 keeps the agent's own correct past trajectories in a lookup memory. C2 fine-tunes the model (LoRA) on exactly the same trajectories.
- **Five attacks:** a hidden instruction inside a retrieved passage; a jailbreak aimed at a confidential code in the system prompt; a question whose evidence was removed (does it invent a citation?); a multi-hop question with one hop removed (does it answer anyway?); and a passage edited so the correct answer changes (does it follow the evidence or its memory?).
- **Memory poisoning:** a few fake episodes (1, 5 or 25) slipped into the memory or the fine-tuning set, to see which route is easier to corrupt.

## What I would want a reader to know first

- The 1.7B model is weak (about a quarter of clean questions answered exactly), so many attacks never get a chance to work. Every rate is reported both unconditionally and conditional on the clean question being answered, and an oracle-context run hands the model the right passages directly.
- Greedy decoding is deterministic on the Mac; on CUDA it is only deterministic with one request per server, which is how all Kaggle runs were served. Differences are judged over questions with paired exact tests.
- The pre-registered LLM judge for claim support failed validation, so no claim-support rate is reported (details in `RESULTS.md`).
- Retrieval is plain BM25 over HotpotQA. The attacks are synthetic.

## Run it

```
python -m venv ~/.venvs/ragbench && ~/.venvs/ragbench/bin/pip install rank-bm25 sentence-transformers peft accelerate pyyaml pytest requests sentencepiece
~/.venvs/ragbench/bin/python -m pytest tests -q                       # no GPU or model needed
llama-server -m <qwen3-1.7b q8_0 gguf> --port 8080 -ngl 99 -c 24576 -np 4 --jinja --cache-ram 256
~/.venvs/ragbench/bin/python -m ragbench.run --config configs/s17_react_c0.yaml
~/.venvs/ragbench/bin/python -m ragbench.analyze results/s17_react_c0 --out results/s17_react_c0/summary.md
```

Data: fetch the HotpotQA distractor validation parquet into `data/hotpot_val.parquet` (not committed; URL and sha256 in `SETUP.md`). `python -m ragbench.data` writes the fixed train, eval and dev splits.

## How the work was organised

Code was written and reviewed by AI models under one lead, with every claim of "done" re-run before it counted; the full evidence log is `reports/EVIDENCE.md`. GPU work ran on free Kaggle T4 sessions through `kaggle/driver.py`.

## Licence
Code: Apache-2.0 (`LICENSE`). Files derived from HotpotQA (questions, passages, episodes under `data/`) follow the HotpotQA licence, CC BY-SA 4.0.
