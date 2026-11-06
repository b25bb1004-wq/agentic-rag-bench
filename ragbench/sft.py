"""Prepare memory-free training conversations from selected episodes."""
import json
from pathlib import Path

from ragbench.agents.common import SYSTEM_PROMPT
from ragbench.memory import select_episodes


def build_sft(episodes):
    selected = select_episodes(episodes)
    records = []
    for episode in selected:
        messages = json.loads(episode.trajectory.raw)
        if not isinstance(messages, list) or not messages:
            raise ValueError("trajectory.raw must be a nonempty message list")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"} or not isinstance(message.get("content"), str):
                raise ValueError("invalid conversation message")
        if not any(m["role"] == "assistant" for m in messages):
            raise ValueError("conversation has no assistant response")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [dict(m) for m in messages if m["role"] != "system"]
        records.append({"messages": messages})
    assert len(records) == len(selected)
    return records


def write_jsonl(records, path):
    with Path(path).open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
