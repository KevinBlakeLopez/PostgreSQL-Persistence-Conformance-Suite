# Run with cwd = <investigator-venv>/lib/python3.13/site-packages (the venv behind the recorded runs).
import base64, csv, hashlib, os
bad, ok, missing = [], 0, []
with open("sqlalchemy-2.1.5.dist-info/RECORD", newline="") as f:
    for path, h, size in csv.reader(f):
        if not h or not path.startswith("sqlalchemy/"):
            continue
        algo, digest = h.split("=", 1)
        try:
            data = open(path, "rb").read()
        except FileNotFoundError:
            missing.append(path); continue
        d = base64.urlsafe_b64encode(hashlib.new(algo, data).digest()).rstrip(b"=").decode()
        if d != digest:
            bad.append(path)
        else:
            ok += 1
print("sqlalchemy files matching RECORD:", ok, "| mismatched:", bad, "| missing:", missing[:5])
