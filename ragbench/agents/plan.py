"""Plan sub-questions, retrieve evidence, then answer."""
from __future__ import annotations

import json
import re

from ragbench.agents.common import DUPLICATE_SEARCH, INVALID_REPLY, OBSERVATION_STOP, build_system, clip_reply, format_obs, normalize_query, parse_final, parse_search
from ragbench.schema import OBS_CHARS, Passage, Step, Trajectory

PLAN_ASK = "\nFirst list up to 3 sub-questions, one per line, each starting with 'Q:'"
FINAL_ASK = "\n\nGive your Final: <short answer> | Cite: <id1>,<id2> line now."


class PlanAgent:
    def __init__(self, k=3, max_sub=3):
        self.k = k
        self.max_sub = max_sub

    def run(self, question, retriever, llm, memory_block="", system_extra="", overlay=None, seed=0, prefetch: list[Passage] | None = None) -> Trajectory:
        messages = [
            {"role": "system", "content": build_system(memory_block, system_extra)},
            {"role": "user", "content": question + PLAN_ASK},
        ]
        steps = []
        retrieved_ids = []
        searched_queries = set()
        if prefetch is not None:
            obs = "\n".join(f"[{p.id}] {p.text[:OBS_CHARS]}" for p in prefetch)
            steps.append(Step("search", "<prefetch>", obs))
            retrieved_ids = list(dict.fromkeys(p.id for p in prefetch))
            messages.append({"role": "user", "content": f"Observation: {obs}"})
        plan = clip_reply(llm.chat(messages, max_tokens=200, temperature=0.0, seed=seed, stop=OBSERVATION_STOP))
        n_llm_calls = 1
        messages.append({"role": "assistant", "content": plan})
        sub_questions = [match.group(1).strip() for match in re.finditer(r"^\s*Q:[^\S\n]*(.+)$", plan, re.MULTILINE) if match.group(1).strip()]
        sub_questions = sub_questions[:self.max_sub] or [question]
        query = parse_search(plan)
        if query is not None:
            sub_questions = [query]
        observations = []
        for subq in sub_questions:
            normalized = normalize_query(subq)
            if normalized in searched_queries:
                messages.append({"role": "user", "content": DUPLICATE_SEARCH})
                continue
            searched_queries.add(normalized)
            steps.append(Step("plan", subq, ""))
            results = retriever.search(subq, self.k, overlay)
            obs = format_obs(results)
            steps.append(Step("search", subq, obs))
            observations.append(f"Q: {subq}\nObservation: {obs}")
            for passage, _ in results:
                if passage.id not in retrieved_ids:
                    retrieved_ids.append(passage.id)
        messages.append({"role": "user", "content": question + "\n\n" + "\n\n".join(observations) + FINAL_ASK})
        final = None
        # Bound follow-up searches while giving each one a fresh answer turn.
        for turn in range(self.max_sub + 1):
            reply = clip_reply(llm.chat(messages, max_tokens=200, temperature=0.0, seed=seed, stop=OBSERVATION_STOP))
            n_llm_calls += 1
            messages.append({"role": "assistant", "content": reply})
            query = parse_search(reply) if turn < self.max_sub else None
            if query is None:
                final = parse_final(reply)
                if final is not None or turn == self.max_sub:
                    break
                messages.append({"role": "user", "content": INVALID_REPLY})
                continue
            normalized = normalize_query(query)
            if normalized in searched_queries:
                messages.append({"role": "user", "content": DUPLICATE_SEARCH})
                continue
            searched_queries.add(normalized)
            results = retriever.search(query, self.k, overlay)
            obs = format_obs(results)
            steps.append(Step("search", query, obs))
            for passage, _ in results:
                if passage.id not in retrieved_ids:
                    retrieved_ids.append(passage.id)
            messages.append({"role": "user", "content": f"Observation: {obs}\n\nGive your Final answer now."})
        answer, citations, abstained = final if final is not None else ("", [], False)
        steps.append(Step("answer", answer, ""))
        return Trajectory(
            qid="", question=question, answer=answer, citations=citations,
            steps=steps, retrieved_ids=retrieved_ids, raw=json.dumps(messages),
            n_llm_calls=n_llm_calls, abstained=abstained, parse_failed=final is None,
        )
