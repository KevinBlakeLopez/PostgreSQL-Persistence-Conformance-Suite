"""Extract and cross-check CHK-5's server log. Not part of the upstream issue.

    python -I server_log_check.py extract <docker-logs-file> output/server-log-extract.txt
    python -I server_log_check.py query output        # prints the psql query for the printed IDs
    python -I server_log_check.py check output > output/server-log-check.txt

extract keeps every log entry, with its continuation lines, whose application_name is a
subject session: repro-tortoise, repro-django or repro-sqlalchemy. The witness and admin
sessions are left out.

check groups each subject session's statements into transactions (BEGIN to COMMIT or
ROLLBACK), takes the transaction ID from the line that ends it, and attaches the rows that
auto_explain reports for each INSERT and UPDATE: the actual rows of the node under the
Insert or Update node, that is, the rows inserted, or the rows the UPDATE matched. It
matches every transaction to the run, arm and transaction that printed the same ID in
output/*.out, and to that ID's fate in output/psql-xact-status.txt. It exits 1 if a
printed ID has no transaction, a transaction with an ID was printed by no run (DDL setup
transactions excepted), the program's fate and psql's differ, or the ending statement
does not match the fate.
"""

import collections
import pathlib
import re
import sys

SUBJECTS = ("repro-tortoise", "repro-django", "repro-sqlalchemy")
ENTRY = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} UTC \[(\d+)\] app=(\S*) xid=(\d+) ([A-Z]+):\s+(.*)$")
PRINTED = re.compile(r"^\s+(?:(first|second|outer) )?transaction: pg_xact_status\((\d+)\) (\w+)")
ARM = re.compile(r"^([a-z_-]+): ")
END = {"COMMIT": "committed", "COMMIT;": "committed", "ROLLBACK": "aborted", "ROLLBACK;": "aborted"}


def entries(path):
    current = None
    for line in pathlib.Path(path).read_text().splitlines():
        m = ENTRY.match(line)
        if m:
            if current:
                yield current
            pid, app, xid, kind, text = m.groups()
            current = {"pid": pid, "app": app, "xid": int(xid), "kind": kind, "lines": [text], "raw": [line]}
        elif current is not None and line.startswith("\t"):
            current["lines"].append(line[1:])
            current["raw"].append(line)
        else:
            if current:
                yield current
            current = None
    if current:
        yield current


def extract(log, out):
    kept = [e for e in entries(log) if e["app"] in SUBJECTS]
    pathlib.Path(out).write_text("".join(line + "\n" for e in kept for line in e["raw"]))
    print(f"kept {len(kept)} entries of sessions {', '.join(SUBJECTS)}", file=sys.stderr)


def printed_ids(outdir):
    ids = {}
    for path in sorted(pathlib.Path(outdir).glob("*.rep*.out")):
        arm = None
        for line in path.read_text().splitlines():
            m = ARM.match(line)
            if m and m.group(1) != "versions":
                arm = m.group(1)
            m = PRINTED.match(line)
            if m:
                ids[int(m.group(2))] = (path.name[: -len(".out")], arm, m.group(1) or "only", m.group(3))
    return ids


def query(outdir):
    rows = ",".join(f"('{run}','{arm}','{label}',{xid})" for xid, (run, arm, label, _) in sorted(printed_ids(outdir).items()))
    print("select run, arm, tx, xid, pg_xact_status(xid::text::xid8) as fate from (values "
          f"{rows}) as t(run, arm, tx, xid) order by xid")


def transactions(extract_path):
    open_tx, done = {}, []
    for e in entries(extract_path):
        tx = open_tx.get(e["pid"])
        text = e["lines"][0]
        if e["kind"] == "LOG" and re.match(r"^(statement|execute [^:]+):", text):
            sql = re.sub(r"^(statement|execute [^:]+):\s*", "", text).strip()
            sql_full = " ".join([sql] + [l.strip() for l in e["lines"][1:]])
            if sql in ("BEGIN", "BEGIN;"):
                tx = open_tx[e["pid"]] = {"pid": e["pid"], "app": e["app"], "stmts": []}
            if tx is None:
                continue
            tx["stmts"].append({"sql": sql_full, "params": "", "rows": None})
            if sql in END:
                tx["xid"], tx["end"] = e["xid"], sql.rstrip(";")
                done.append(open_tx.pop(e["pid"]))
        elif tx is not None and e["kind"] == "DETAIL" and text.startswith("Parameters: "):
            tx["stmts"][-1]["params"] = text[len("Parameters: "):]
        elif tx is not None and e["kind"] == "LOG" and text.startswith("duration: ") and "plan:" in text:
            plan = e["lines"][1:]
            for i, node in enumerate(plan):
                if re.match(r"^(Insert|Update|Delete) on ", node) and i + 1 < len(plan):
                    m = re.search(r"\(actual rows=([\d.]+) loops=\d+\)", plan[i + 1])
                    target = next((s for s in reversed(tx["stmts"]) if re.match(r"^(INSERT|UPDATE|DELETE)", s["sql"]) and s["rows"] is None), None)
                    if m and target is not None:
                        target["rows"] = float(m.group(1))
        # transactions still open when the extract ends are dropped, and reported below
    return done, open_tx


def token(stmt):
    sql = stmt["sql"]
    word = sql.split()[0].upper().rstrip(";")
    if word in ("BEGIN", "COMMIT", "SAVEPOINT", "RELEASE"):
        return word
    if word == "ROLLBACK":
        return "ROLLBACK TO" if re.match(r"(?i)^ROLLBACK TO", sql) else "ROLLBACK"
    if word in ("INSERT", "UPDATE", "DELETE"):
        rows = "?" if stmt["rows"] is None else f"{stmt['rows']:g}"
        where = ""
        if word == "UPDATE":
            m = re.search(r'"id"\s*=\s*(\d+)', sql)
            if m:
                where = f" id={m.group(1)}"
            elif re.search(r'"id"\s*=\s*\$\d+', sql) and stmt["params"]:
                where = f" id={stmt['params'].split('=')[-1].strip().strip(chr(39))}"
        return f"{word}{where} [{rows} rows]"
    if word == "CREATE":
        return "CREATE"
    return "SELECT" if word in ("SELECT", "WITH", "") or sql == "" else word


def check(outdir):
    outdir = pathlib.Path(outdir)
    printed = printed_ids(outdir)
    fates = {}
    for line in (outdir / "psql-xact-status.txt").read_text().splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) == 5 and cells[3].isdigit():
            fates[int(cells[3])] = cells[4]
    done, still_open = transactions(outdir / "server-log-extract.txt")

    problems, seen, setup = [], set(), 0
    groups = collections.defaultdict(collections.Counter)
    print(f"{'run':<22} {'arm':<29} {'tx':<6} {'pid':>4} {'xid':>4}  {'statements, with auto_explain rows for INSERT and UPDATE':<84} {'script':<10} psql")
    for tx in done:
        tokens = [token(s) for s in tx["stmts"]]
        if tx["xid"] not in printed:
            if any(t == "CREATE" for t in tokens) or tx["xid"] == 0:
                setup += 1
                continue
            problems.append(f"transaction {tx['xid']} (pid {tx['pid']}, {tx['app']}) was printed by no run")
            continue
        seen.add(tx["xid"])
        run, arm, label, script_fate = printed[tx["xid"]]
        psql_fate = fates.get(tx["xid"], "?")
        ok = script_fate == psql_fate == END[tx["end"]]
        if not ok:
            problems.append(f"transaction {tx['xid']}: script {script_fate}, psql {psql_fate}, ended with {tx['end']}")
        shown = " ".join(t for t in tokens if t != "SELECT")
        program = run.split(".")[0]
        groups[(program, arm, label)][re.sub(r" id=[0-9]+", " id=<pk>", shown)] += 1
        print(f"{run:<22} {arm:<29} {label:<6} {tx['pid']:>4} {tx['xid']:>4}  {shown:<84} {script_fate:<10} {psql_fate}{'' if ok else '  <-- MISMATCH'}")
    for xid in sorted(set(printed) - seen):
        problems.append(f"printed transaction {xid} {printed[xid][:3]} was not found in the server log")
    for pid, tx in still_open.items():
        problems.append(f"pid {pid} ({tx['app']}) has a transaction still open at the end of the extract")

    print("\nStatement patterns by program, arm and transaction, with how many runs showed each:")
    for (program, arm, label), counter in sorted(groups.items()):
        for pattern, n in sorted(counter.items()):
            print(f"  {program:<16} {arm:<29} {label:<6} {n:>3} x  {pattern}")
    print(f"\n{len(done)} subject transactions: {len(seen)} matched to printed IDs, {setup} setup or read-only;"
          f" {len(printed)} IDs printed; {len(fates)} fates read by psql; problems: {len(problems)}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "extract" and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif command == "query" and len(sys.argv) == 3:
        query(sys.argv[2])
    elif command == "check" and len(sys.argv) == 3:
        check(sys.argv[2])
    else:
        sys.exit(__doc__)
