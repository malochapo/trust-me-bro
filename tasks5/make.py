#!/usr/bin/env python3
"""Builds tasks5/: pilot 4's two long sessions with the /compact moved.

Each tasks4/long-* task is seven messages over two unrelated investigations, with a /compact
between them (after message 3). Its variants keep every message and grader and change only
where the /compact goes:
  -c0  no /compact
  -c2  after message 2, in the middle of the first investigation
  -c3  after message 3, between the two investigations (tasks4's own position)
  -c5  after message 5, in the middle of the second investigation

Usage: python3 -I tasks5/make.py   (rewrites tasks5/<task>-c<N>/ from tasks4/)
"""

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "tasks4"
TASKS = ("long-incident-then-dedup", "long-security-then-redaction")
POSITIONS = {0: "no /compact", 2: "/compact after message 2, in the middle of the first investigation",
             3: "/compact after message 3, between the two investigations (tasks4's position)",
             5: "/compact after message 5, in the middle of the second investigation"}


def variant(task, position):
    messages = [m for m in task["followups"] if m != "/compact"]
    assert len(messages) == len(task["followups"]) - 1 == 6, "expected six follow-ups and one /compact"
    if position:
        messages.insert(position - 1, "/compact")  # message 1 is the prompt
    return {**task, "id": f"{task['id']}-c{position}", "followups": messages,
            "notes": f"Compaction position test ({POSITIONS[position]}). {task['notes']}"}


def main():
    for name in TASKS:
        task = json.loads((SOURCE / name / "task.json").read_text())
        for position in POSITIONS:
            out = HERE / f"{name}-c{position}"
            shutil.rmtree(out, ignore_errors=True)
            shutil.copytree(SOURCE / name, out)
            (out / "task.json").write_text(json.dumps(variant(task, position), indent=2) + "\n")
            print(out.relative_to(HERE.parent))


if __name__ == "__main__":
    main()
