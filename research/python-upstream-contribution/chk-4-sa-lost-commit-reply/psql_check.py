# CHK-4: read every run's xids with psql inside the container (as postgres, over the Unix socket), and
# compare those fates and the marker rows with what the program reported. Run from output/ on
# 2026-10-25, as a heredoc, while ppcs-chk4-pg was up; saved afterwards with only this header added.
# Writes psql-xact-status.txt, psql-item-rows.txt and psql-check.txt. The container is gone, so it
# cannot be re-run as is.
import glob, json, os, subprocess
env = {**os.environ, "DOCKER_CONTEXT": "colima"}
runs = []
for raw_path in sorted(glob.glob("sa-*/raw/*.json")):
    raw = json.load(open(raw_path)); out = json.load(open(raw_path.replace("/raw/", "/")[:-5] + ".out"))
    runs.append((raw_path, raw, out))
xids = sorted({r["unit1"]["xid"] for _, r, _ in runs} | {r["unit2"]["xid"] for _, r, _ in runs}, key=int)
def psql(sql):
    return subprocess.run(["docker", "exec", "ppcs-chk4-pg", "psql", "-X", "-A", "-t", "-F", " ", "-U", "postgres", "-d", "chk4", "-c", sql],
                          env=env, capture_output=True, text=True, check=True).stdout
status = psql("select x, pg_xact_status(x::xid8) from unnest(array[%s]::text[]) as x order by x::bigint" % ",".join(f"'{x}'" for x in xids))
open("psql-xact-status.txt", "w").write("# psql inside the container, as postgres: xid and pg_xact_status(xid)\n" + status)
fates = dict(line.split() for line in status.strip().splitlines())
rows = psql("select tag, xmin::text from chk4_item order by id")
open("psql-item-rows.txt", "w").write("# psql inside the container, as postgres: every chk4_item row (tag, xmin), including the smoke runs'\n" + rows)
xmin = dict(line.split() for line in rows.strip().splitlines())
lines, bad = [], 0
for raw_path, raw, out in runs:
    u1, u2, (t1, t2) = raw["unit1"], raw["unit2"], raw["tags"]
    problems = []
    if fates[u1["xid"]] != out["unit1"]["fate_at_report"] or fates[u1["xid"]] != out["unit1_final"]["fate"]:
        problems.append("unit 1 fate differs from the program's")
    if fates[u2["xid"]] != out["unit2"]["fate"]:
        problems.append("unit 2 fate differs")
    expect_row = raw["arm"] != "rejected"
    if (t1 in xmin) != expect_row or (expect_row and xmin[t1] != u1["xid"]):
        problems.append("unit 1's row is not as expected")
    if xmin.get(t2) != u2["xid"]:
        problems.append("unit 2's row is not as expected")
    bad += bool(problems)
    lines.append(f"{os.path.basename(raw_path)[:-5]:32} sa-{raw['sqlalchemy']} unit1 psql={fates[u1['xid']]:9} program@report={out['unit1']['fate_at_report']:9} "
                 f"row={'xmin=unit1' if t1 in xmin and xmin[t1]==u1['xid'] else 'absent'}  unit2 psql={fates[u2['xid']]}  {'OK' if not problems else 'FAIL: ' + '; '.join(problems)}")
lines.append(f"{len(runs)} runs; {len(xids)} xids read with psql; runs where psql and the program disagree: {bad}")
open("psql-check.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines[:3] + ["..."] + lines[-1:]))
