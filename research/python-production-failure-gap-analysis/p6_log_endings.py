"""For each P6 run, find the subject session (the backend that inserted the marker) in the
server log (log_statement=all) and print the transaction-control statements it sent."""
import re, sys

log = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
pid_re = re.compile(r"^\S+ \S+ UTC \[(\d+)\]")
by_pid = {}
for line in log:
    m = pid_re.match(line)
    if m:
        by_pid.setdefault(m.group(1), []).append(line)

ctl = re.compile(r"(?:statement|execute [^:]*): (BEGIN[^;]*|COMMIT;?|ROLLBACK;?)\s*$", re.I)
for subj in ("sa-core", "django", "asyncpg", "tortoise"):
    for st in ("57014", "40P01", "40001"):
        for r in (1, 2, 3):
            marker = f"'{subj}-{st}-{r}'"
            for pid, lines in by_pid.items():
                text = "\n".join(lines)
                if marker in text and re.search(r"insert into \"?item", text, re.I):
                    ends = [m.group(1).upper().rstrip(";") for l in lines if (m := ctl.search(l))]
                    print(f"{subj:9s} {st} rep{r} pid {pid}: {' '.join(ends)}")
