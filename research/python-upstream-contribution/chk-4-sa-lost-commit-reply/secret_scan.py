# CHK-4: look for the instance's two passwords in the evidence directory and in the full server log.
# Run on 2026-10-25 as a heredoc, before the container was removed and the instance file deleted;
# saved afterwards with only this header added. Usage: secret_scan.py <instance.json> <dir> <full log>
# The result is in output/secret-scan.txt.
import json, os, sys
inst = json.load(open(sys.argv[1])); secrets = [inst["app_password"], inst["superuser_password"]]
hits = []
for root, _, files in os.walk(sys.argv[2]):
    for f in files:
        p = os.path.join(root, f)
        if any(s in open(p, errors="replace").read() for s in secrets): hits.append(p)
log = open(sys.argv[3], errors="replace").read()
print("password strings found in the evidence directory:", hits or "none")
print("password strings found in the full server log:", [i for i, s in enumerate(secrets) if s in log] or "none")
print("server-log lines mentioning 'password':", sum("password" in l.lower() for l in log.splitlines()))
