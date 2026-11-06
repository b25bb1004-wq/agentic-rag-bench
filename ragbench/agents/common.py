"""Shared prompts and parsers for retrieval agents."""
from __future__ import annotations

import re
from ragbench.schema import OBS_CHARS


OBSERVATION_STOP = ["\nObservation:", "Observation:"]
INVALID_REPLY = "Reply with either Action: search[<query>] or Final: <short answer> | Cite: <ids>"
DUPLICATE_SEARCH = "You already searched that. Use the evidence above and give Final: <short answer> | Cite: <ids>"


def normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def clip_reply(text: str) -> str:
    """Remove model-written tool observations before recording or parsing."""
    match = re.search(r"(?<!\S)Observation:", text)
    return text[:match.start()].rstrip() if match else text.rstrip()


SYSTEM_PROMPT = f"""Answer the multi-hop question using only retrieved passages.
You can use the search tool to gather evidence. For a ReAct turn, write:
Thought: <reasoning about what evidence is needed>
Action: search[<query>]
The environment replies with Observation: followed by up to 3 passages,
each formatted as [<id>] <text truncated to {OBS_CHARS} chars>.
When ready, make the final line exactly:
Final: <short answer> | Cite: <id1>, <id2>
The answer must be as short as possible: a name, number, date, place, or exactly
yes or no for yes/no questions, with no explanation.
If the evidence is insufficient, abstain with:
Final: UNKNOWN | Cite:
Cite passage ids exactly as they appear in observations, for example:
Final: Example answer | Cite: p:Some Title
Never cite a number or an id you have not seen in an Observation. Do not answer from memory."""


def build_system(memory_block: str, system_extra: str) -> str:
    prompt = SYSTEM_PROMPT
    if memory_block:
        prompt += f"\n\nPast experience (may help):\n{memory_block}"
    if system_extra:
        prompt += f"\n\n{system_extra}"
    return prompt


def refusal_like(answer: str) -> bool:
    return bool(re.match(r"^(?:i cannot\b|i can't\b|not enough information\b|no information\b|cannot determine\b|unable to\b)", answer.strip(), re.IGNORECASE))


def parse_final(text: str) -> tuple[str, list[str], bool] | None:
    matches = list(re.finditer(r"^[^\S\n]*Final:[^\S\n]*", text, re.MULTILINE | re.IGNORECASE))
    if not matches:
        return None
    remainder = text[matches[-1].end():]
    cite = re.search(r"Cite:[^\S\n]*([^\n]*)", remainder, re.IGNORECASE)
    if cite:
        answer = remainder[:cite.start()].rstrip(" \t\r\n|.;,")
        raw_ids = cite.group(1)
    else:
        answer = remainder.split("\n", 1)[0].strip()
        raw_ids = ""
    if answer.upper() == "UNKNOWN.":
        answer = answer[:-1]
    parts = re.split(r",\s*(?=p:)", raw_ids) if "p:" in raw_ids else raw_ids.split(",")
    citations = [part.strip() for part in parts if part.strip()]
    return answer, citations, answer.upper() in {"UNKNOWN", ""} or refusal_like(answer)


def parse_search(text: str) -> str | None:
    match = re.search(r"^[^\S\n]*Action:[^\S\n]*search\[(.*)\]", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def format_obs(results) -> str:
    return "\n".join(f"[{passage.id}] {passage.text[:OBS_CHARS]}" for passage, _ in results[:3])
