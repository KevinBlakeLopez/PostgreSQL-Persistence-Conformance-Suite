"""Compare CHK-4's outputs: repetitions byte for byte, and SQLAlchemy 2.1.5 against 2.1.6.

Run from output/. Writes comparison.txt (the SHA-256 of each run's stdout, per cell) and
versions-compare.txt (each cell's repetition 1 on both versions, compared apart from the version field).
"""
import collections
import glob
import hashlib
import json
import os

cells = collections.defaultdict(dict)
for path in sorted(glob.glob("sa-*/*.out")):
    version, name = path.split("/")
    cell, rep = name.rsplit(".rep", 1)
    cells[(version, cell)][rep[:-4]] = hashlib.sha256(open(path, "rb").read()).hexdigest()
lines = ["Repetitions compared byte for byte (SHA-256 of each run's stdout).", "cell | rep1 | rep2 | rep3 | identical"]
bad = 0
for (version, cell), reps in sorted(cells.items()):
    same = len(set(reps.values())) == 1 and len(reps) == 3
    bad += not same
    lines.append(f"{version} {cell} | {reps.get('1', '-')[:12]} | {reps.get('2', '-')[:12]} | {reps.get('3', '-')[:12]} | "
                 f"{'yes' if same else 'NO'}")
lines.append(f"{len(cells)} cells, {sum(len(r) for r in cells.values())} runs; cells whose repetitions differ: {bad}")
open("comparison.txt", "w").write("\n".join(lines) + "\n")

lines, diff = [], 0
for path in sorted(glob.glob("sa-2.1.6/*.rep1.out")):
    a, b = json.load(open(path)), json.load(open(path.replace("sa-2.1.6", "sa-2.1.5")))
    a.pop("sqlalchemy")
    b.pop("sqlalchemy")
    diff += a != b
    lines.append(f"{os.path.basename(path)[:-9]:26} 2.1.5 vs 2.1.6 apart from the version field: "
                 f"{'identical' if a == b else 'DIFFERENT'}")
lines.append(f"cells that differ between versions: {diff}")
open("versions-compare.txt", "w").write("\n".join(lines) + "\n")
print(open("comparison.txt").read().splitlines()[-1])
print(lines[-1])
