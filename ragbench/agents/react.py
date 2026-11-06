"""ReAct agent with a bounded search loop."""
from __future__ import annotations

import json

from ragbench.agents.common import DUPLICATE_SEARCH, INVALID_REPLY, OBSERVATION_STOP, build_system, clip_reply, format_obs, normalize_query, parse_final, parse_search
from ragbench.schema import OBS_CHARS, Passage, Step, Trajectory

SEARCH_BUDGET_DONE = "Search budget used. Give your Final answer now."


class ReActAgent:
    """ReAct agent with a bounded search loop. `should_stop` is a Python-only hook (YAML configs cannot pass a callable)."""
    def __init__(self, max_steps=6, k=3, min_searches=1, max_searches=None, should_stop=None):
        self.max_steps = max_steps
        self.k = k
        self.min_searches = min_searches
        self.max_searches = max_searches  # None = unbounded within max_steps; set for the retrieval-budget sweep
        self.should_stop = should_stop  # optional callable(question, steps, n_searches) -> bool; True ends retrieval like the budget

    def run(self, question, retriever, llm, memory_block="", system_extra="", overlay=None, seed=0, prefetch: list[Passage] | None = None) -> Trajectory:
        messages = [
            {"role": "system", "content": build_system(memory_block, system_extra)},
            {"role": "user", "content": question},
        ]
        steps = []
        retrieved_ids = []
        searches_done = 0
        searched_queries = set()
        if prefetch is not None:
            obs = "\n".join(f"[{p.id}] {p.text[:OBS_CHARS]}" for p in prefetch)
            steps.append(Step("search", "<prefetch>", obs))
            retrieved_ids = list(dict.fromkeys(p.id for p in prefetch))
            messages.append({"role": "user", "content": f"Observation: {obs}"})
            searches_done += 1
        stopped = prefetch is not None and self.should_stop is not None and self.should_stop(question, steps, searches_done)
        n_llm_calls = 0
        final = None
        # Reserve the existing extra answer turn only after sufficient retrieval.
        for turn in range(self.max_steps + 1):
            if turn == self.max_steps:
                if final is not None or searches_done < self.min_searches:
                    break
                messages.append({"role": "user", "content": "Give your Final answer now."})
            reply = clip_reply(llm.chat(messages, max_tokens=200, temperature=0.0, seed=seed, stop=OBSERVATION_STOP))
            n_llm_calls += 1
            messages.append({"role": "assistant", "content": reply})
            query = parse_search(reply) if turn < self.max_steps else None
            if query is None:
                final = parse_final(reply)
                if final is not None:
                    if searches_done >= self.min_searches:
                        break
                    final = None
                    nudge = "You must call search[<query>] at least once before giving Final. Search now."
                else:
                    nudge = INVALID_REPLY
                if turn < self.max_steps:
                    messages.append({"role": "user", "content": nudge})
                continue
            if stopped or (self.max_searches is not None and searches_done >= self.max_searches):
                messages.append({"role": "user", "content": SEARCH_BUDGET_DONE})
                continue
            normalized = normalize_query(query)
            if normalized in searched_queries:
                messages.append({"role": "user", "content": DUPLICATE_SEARCH})
                continue
            searched_queries.add(normalized)
            results = retriever.search(query, self.k, overlay)
            searches_done += 1
            obs = format_obs(results)
            steps.append(Step("search", query, obs))
            for passage, _ in results:
                if passage.id not in retrieved_ids:
                    retrieved_ids.append(passage.id)
            messages.append({"role": "user", "content": f"Observation: {obs}"})
            stopped = self.should_stop is not None and self.should_stop(question, steps, searches_done)
        answer, citations, abstained = final if final is not None else ("", [], False)
        steps.append(Step("answer", answer, ""))
        return Trajectory(
            qid="", question=question, answer=answer, citations=citations,
            steps=steps, retrieved_ids=retrieved_ids, raw=json.dumps(messages),
            n_llm_calls=n_llm_calls, abstained=abstained, parse_failed=final is None,
        )
