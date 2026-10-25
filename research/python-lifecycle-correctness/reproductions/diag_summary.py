"""Tabulate the diagnostic registry line ("diag: at lifespan shutdown: ...") per case and repetition.

Usage: python diag_summary.py ../outputs/diag-run1
"""

import re
import sys
from collections import Counter
from pathlib import Path

LINE = re.compile(r"diag: at lifespan shutdown: (\d+) connection\(s\) registered (\[.*?\]), (\d+) task\(s\), (\d+) not done")


def main() -> None:
    print("| Case | Reps | Registry at the lifespan boundary (connections [transport state], tasks, not done) |")
    print("| --- | --- | --- |")
    for case_dir in sorted(p for p in Path(sys.argv[1]).iterdir() if p.is_dir()):
        seen: Counter[str] = Counter()
        reps = sorted(case_dir.glob("rep-*.server.log"))
        for log in reps:
            match = LINE.search(log.read_text())
            seen[f"{match[1]} {match[2]}, {match[3]} task(s), {match[4]} not done" if match else "no diag line"] += 1
        name = case_dir.name.split("Z-", 1)[-1]
        print(f"| {name} | {len(reps)} | {'; '.join(f'{k} ×{v}' for k, v in seen.items())} |")


if __name__ == "__main__":
    main()
