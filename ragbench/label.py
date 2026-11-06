"""Interactive blind labelling for judge validation. Resumable. Lead-owned.

  python -m ragbench.label            # reads data/judge_to_label.jsonl, writes data/judge_validation.jsonl
Keys: y = answer fully supported by the passages, n = not supported, s = skip, q = quit (progress is saved after every answer).
Rule: judge ONLY from the passages shown, never from your own knowledge of the world.
"""
import argparse, json, textwrap
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/judge_to_label.jsonl")
    ap.add_argument("--out", default="data/judge_validation.jsonl")
    ap.add_argument("--only", help="file with one item id per line: label just these (operator review set)")
    a = ap.parse_args()
    items = [json.loads(l) for l in Path(a.src).read_text().splitlines() if l.strip()]
    if a.only:
        keep = {line.strip() for line in Path(a.only).read_text().splitlines() if line.strip()}
        items = [i for i in items if str(i["id"]) in keep]
    out = Path(a.out)
    done = {json.loads(l)["id"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    todo = [i for i in items if i["id"] not in done]
    print(f"{len(done)} labelled, {len(todo)} to go. y=supported n=not supported s=skip q=quit")
    for k, it in enumerate(todo, 1):
        print(f"\n--- {len(done) + k}/{len(items)} ---\nQUESTION: {it['question']}\nANSWER:   {it['answer']}")
        for j, p in enumerate(it["passages"], 1):
            print(f"PASSAGE {j}: " + textwrap.fill(p, 110, subsequent_indent="           "))
        while True:
            try:
                key = input("supported by the passages? [y/n/s/q] ").strip().lower()
            except EOFError:  # no keyboard attached (e.g. Claude Code's ! prefix): stop cleanly, progress is kept
                print("\nNo interactive input. Run this in the Terminal app instead.")
                key = "q"
            if key in ("y", "n", "s", "q"):
                break
        if key == "q":
            break
        if key == "s":
            continue
        with out.open("a") as f:
            f.write(json.dumps({**it, "label": key == "y"}) + "\n")
    print("saved to", out)


if __name__ == "__main__":
    main()
