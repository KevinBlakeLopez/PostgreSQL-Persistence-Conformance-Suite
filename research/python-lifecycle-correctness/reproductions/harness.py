"""Run one lifecycle case against a real server process and record what an outside observer sees.

The harness is the application's backend (see backend_link.py): a TCP service
in this process that logs every line the application sends and answers each
``CALL`` with ``OK`` after a configurable delay, standing in for a remote
service's latency. Whether cleanup finished is decided from this log and from
the server's exit status, not from the server's own messages.

Sequence for each repetition:

1. start the server as a child process (no shell), with the lifespan on;
2. wait until lifespan startup has reached the backend, then until the HTTP
   port accepts connections;
3. send one HTTP request and wait until its unit of work has reached the
   backend (a barrier, not a sleep);
4. send the signal to the server process;
5. wait for the process to exit (SIGKILL after a hard limit, recorded as hung),
   then until every backend connection has closed;
6. write the raw evidence to a new directory under outputs/.

With ``--hold-startup`` the backend withholds its answer to lifespan startup;
the signal is sent while startup is waiting, and the answer is released only
after the signal was delivered.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent / "outputs"

REQUESTS = {
    "asgi": b"GET / HTTP/1.1\r\nHost: t\r\nConnection: close\r\n\r\n",
    "fastapi": b"POST /jobs HTTP/1.1\r\nHost: t\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
}
UNIT = {"asgi": "request", "fastapi": "job"}


class Backend:
    def __init__(self, delays: dict[str, float], hold_startup: bool) -> None:
        self.delays = delays
        self.startup_gate = threading.Event()
        if not hold_startup:
            self.startup_gate.set()
        self.events: list[tuple[float, int, str]] = []
        self.open_connections = 0
        self.pending_answers = 0
        self.cond = threading.Condition()
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _record(self, conn_id: int, line: str) -> None:
        with self.cond:
            self.events.append((time.time(), conn_id, line))
            self.cond.notify_all()

    def _accept(self) -> None:
        conn_id = 0
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            conn_id += 1
            with self.cond:
                self.open_connections += 1
            threading.Thread(target=self._serve, args=(conn, conn_id), daemon=True).start()

    def _answer(self, conn: socket.socket, conn_id: int, tag: str, who: str, send_lock: threading.Lock,
                closed: threading.Event) -> None:
        # Each CALL is answered on its own thread, so a long "work" call does not stop the
        # backend from reading (and logging) the release that follows it on the same connection.
        # The reply names its call, and every reply is logged, so "the backend answered the
        # release" is recorded separately from "the application went on after the answer".
        try:
            if tag == "startup":
                while not self.startup_gate.wait(0.05):
                    if closed.is_set():
                        self._record(conn_id, f"REPLY-ABANDONED {tag} {who}")
                        return
            if closed.wait(self.delays.get(tag, 0.0)):
                self._record(conn_id, f"REPLY-ABANDONED {tag} {who}")
                return
            try:
                with send_lock:
                    conn.sendall(f"OK {tag}\n".encode())
                self._record(conn_id, f"REPLY {tag} {who}")
            except OSError as exc:
                self._record(conn_id, f"REPLY-FAILED {tag} {who} {type(exc).__name__}")
        finally:
            with self.cond:
                self.pending_answers -= 1
                self.cond.notify_all()

    def _serve(self, conn: socket.socket, conn_id: int) -> None:
        send_lock = threading.Lock()
        closed = threading.Event()
        answers: list[threading.Thread] = []
        try:
            for raw in conn.makefile("rb"):
                line = raw.decode().strip()
                self._record(conn_id, line)
                kind, tag, who = line.split(" ", 2)
                if kind == "CALL":
                    with self.cond:
                        self.pending_answers += 1
                    answer = threading.Thread(target=self._answer, args=(conn, conn_id, tag, who, send_lock, closed),
                                              daemon=True)
                    answers.append(answer)
                    answer.start()
        except (ConnectionError, OSError) as exc:
            self._record(conn_id, f"ERROR {type(exc).__name__}")
        finally:
            self._record(conn_id, "EOF")
            closed.set()
            # Close only after this connection's pending answers gave up, so none of them
            # writes to a descriptor the operating system has already reused.
            for answer in answers:
                answer.join(5)
            conn.close()
            with self.cond:
                self.open_connections -= 1
                self.cond.notify_all()

    def wait_for(self, predicate, timeout: float) -> bool:
        with self.cond:
            return self.cond.wait_for(predicate, timeout)

    def saw(self, line: str) -> bool:
        return any(event == line for _, _, event in self.events)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_command(args: argparse.Namespace, port: int) -> tuple[list[str], Path]:
    module = f"{args.app}_app:app"
    if args.server == "uvicorn":
        cmd = [args.python, "-m", "uvicorn", module, "--app-dir", str(HERE), "--host", "127.0.0.1",
               "--port", str(port), "--lifespan", "on"]
        if args.timeout is not None:
            cmd += ["--timeout-graceful-shutdown", str(args.timeout)]
    else:
        cmd = [args.python, "-m", "hypercorn", module, "--bind", f"127.0.0.1:{port}"]
        if args.timeout is not None:
            cmd += ["--graceful-timeout", str(args.timeout)]
    return cmd, HERE


def client(port: int, payload: bytes, result: dict) -> None:
    data = b""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=120) as s:
            s.sendall(payload)
            while chunk := s.recv(65536):
                data += chunk
        result["ended"] = "eof"
    except OSError as exc:
        result["ended"] = type(exc).__name__
    result["ended_at"] = time.time()
    result["status_line"] = data.split(b"\r\n", 1)[0].decode(errors="replace")
    result["bytes"] = len(data)


def group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def wait_port(port: int, deadline: float) -> bool:
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.05)
    return False


def run_once(args: argparse.Namespace, rep_dir: Path, rep: int) -> dict:
    backend = Backend({"work": args.work_delay, "release": args.release_delay}, args.hold_startup)
    port = free_port()
    witness_path = rep_dir / f"rep-{rep}.witness.log"
    log_path = rep_dir / f"rep-{rep}.server.log"
    env = dict(os.environ, BACKEND=f"127.0.0.1:{backend.port}", WITNESS=str(witness_path), PYTHONUNBUFFERED="1",
               SHIELD="1" if args.shield else "0", SHARED="1" if args.shared else "0",
               STUBBORN="1" if args.stubborn else "0")
    cmd, cwd = server_command(args, port)
    sig = getattr(signal, f"SIG{args.signal}")
    unit = UNIT[args.app]
    record: dict = {"rep": rep, "command": cmd, "signal": args.signal}
    leftover = False
    t_second_signal = None
    with open(log_path, "wb") as log:
        t_start = time.time()
        # Own process group: the signal goes to the main process only, as an orchestrator sends it
        # to a container's PID 1, but the hard-limit kill takes the whole group, as a container
        # runtime would. A server that runs its app in a child process cannot leave an orphan.
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            if not backend.wait_for(lambda: backend.saw("CALL startup lifespan"), 30):
                raise RuntimeError("lifespan startup never reached the backend")
            client_result: dict = {}
            client_thread = None
            if args.hold_startup:
                t_signal = time.time()
                proc.send_signal(sig)
                # The server's event loop is idle, waiting for the withheld answer, so its handler
                # runs within milliseconds. This margin is not observable from outside; it is the
                # one fixed wait in the harness.
                time.sleep(0.2)
                backend.startup_gate.set()
            else:
                if not wait_port(port, time.time() + 30):
                    raise RuntimeError("server never accepted connections")
                client_thread = threading.Thread(target=client, args=(port, REQUESTS[args.app], client_result))
                client_thread.start()
                if not backend.wait_for(lambda: backend.saw(f"CALL work {unit}"), 30):
                    raise RuntimeError("the unit of work never reached the backend")
                t_signal = time.time()
                proc.send_signal(sig)
                if args.second_signal:
                    # A second signal once the cancelled unit's cleanup has reached the backend
                    # (a barrier), as an operator pressing Ctrl+C again would.
                    if backend.wait_for(lambda: backend.saw(f"CALL release {unit}"), args.hard_limit):
                        t_second_signal = time.time()
                        if proc.poll() is None:
                            proc.send_signal(getattr(signal, f"SIG{args.second_signal}"))
            try:
                proc.wait(timeout=max(0.0, args.hard_limit - (time.time() - t_signal)))
                hung = False
            except subprocess.TimeoutExpired:
                hung = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            t_exit = time.time()
            if group_alive(proc.pid):
                leftover = True
                os.killpg(proc.pid, signal.SIGKILL)
            connections_closed = backend.wait_for(lambda: backend.open_connections == 0, 10)
            answers_settled = backend.wait_for(lambda: backend.pending_answers == 0, 10)
            client_done = True
            if client_thread is not None:
                client_thread.join(10)
                client_done = not client_thread.is_alive()
        finally:
            if proc.poll() is None or group_alive(proc.pid):
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            backend.listener.close()

    events = [(round(t - t_signal, 4), cid, line) for t, cid, line in list(backend.events)]
    client_snapshot = dict(client_result)
    if "ended_at" in client_snapshot:
        client_snapshot["ended_at"] = round(client_snapshot["ended_at"] - t_signal, 4)
    lines = [line for _, _, line in events]

    def first(line: str) -> float | None:
        return next((t for t, _, event in events if event == line), None)

    released_at = first(f"NOTE released {unit}")
    shutdown_at = first("CALL shutdown lifespan")
    record.update(
        returncode=proc.returncode,
        hung=hung,
        leftover_processes=leftover,
        # The observation window is complete only if every backend connection closed, every
        # pending answer settled, and the client finished; otherwise the repetition is inconclusive.
        observation_complete=connections_closed and answers_settled and client_done,
        startup_to_signal_s=round(t_signal - t_start, 3),
        signal_to_exit_s=round(t_exit - t_signal, 3),
        second_signal_after_s=round(t_second_signal - t_signal, 3) if t_second_signal else None,
        client=client_snapshot,
        # Seconds by which the client's HTTP connection outlived the start of lifespan shutdown, as
        # the client saw it. Positive: the connection was still open when shutdown began. The client
        # reads EOF a few milliseconds after the server closes, so only large values are meaningful.
        http_connection_end_minus_lifespan_shutdown_s=(
            round(client_snapshot["ended_at"] - shutdown_at, 4)
            if shutdown_at is not None and "ended_at" in client_snapshot else None
        ),
        backend_events=events,
        # Three separate states of the cleanup: the release reached the backend; the backend
        # answered it; the application received the answer and went on (NOTE released).
        cleanup_started=f"CALL release {unit}" in lines,
        cleanup_acknowledged_by_backend=f"REPLY release {unit}" in lines,
        cleanup_finished=released_at is not None,
        lifespan_shutdown_sent=shutdown_at is not None,
        lifespan_shutdown_before_cleanup_finished=(
            shutdown_at is not None and (released_at is None or shutdown_at < released_at)
        ),
        witness=witness_path.read_text().splitlines() if witness_path.exists() else [],
    )
    return record


def versions(python: str) -> dict:
    code = (
        "import json, sys, platform, importlib.metadata as m\n"
        "out = {'python': sys.version.split()[0], 'implementation': platform.python_implementation()}\n"
        "for p in ('uvicorn', 'starlette', 'fastapi', 'hypercorn', 'anyio', 'h11', 'httptools', 'uvloop'):\n"
        "    try: out[p] = m.version(p)\n"
        "    except m.PackageNotFoundError: pass\n"
        "print(json.dumps(out))\n"
    )
    return json.loads(subprocess.check_output([python, "-I", "-c", code]))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--python", required=True, help="interpreter of the virtual environment under test")
    p.add_argument("--server", choices=["uvicorn", "hypercorn"], default="uvicorn")
    p.add_argument("--app", choices=["asgi", "fastapi"], default="asgi")
    p.add_argument("--signal", choices=["TERM", "INT"], default="TERM")
    p.add_argument("--timeout", type=int, default=None, help="graceful shutdown timeout in seconds")
    p.add_argument("--work-delay", type=float, default=60.0)
    p.add_argument("--release-delay", type=float, default=0.5)
    p.add_argument("--hold-startup", action="store_true")
    p.add_argument("--shield", action="store_true", help="wrap the release in asyncio.shield()")
    p.add_argument("--shared", action="store_true", help="release through a pool that lifespan shutdown closes")
    p.add_argument("--stubborn", action="store_true", help="the unit suppresses cancellation and keeps working")
    p.add_argument("--second-signal", choices=["TERM", "INT"], default=None,
                   help="send this signal once the cancelled unit's cleanup reaches the backend")
    p.add_argument("--hard-limit", type=float, default=20.0)
    p.add_argument("--reps", type=int, default=5)
    args = p.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    case_dir = OUTPUTS / f"{stamp}-{args.case}"
    case_dir.mkdir(parents=True, exist_ok=False)
    meta = {
        "case": args.case,
        "argv": sys.argv[1:],
        "started_utc": stamp,
        "host": {"os": platform.platform(), "machine": platform.machine()},
        "versions": versions(args.python),
        "settings": {k: v for k, v in vars(args).items() if k not in ("case", "python")},
    }
    results = [run_once(args, case_dir, rep) for rep in range(1, args.reps + 1)]
    summary_keys = ("returncode", "hung", "leftover_processes", "observation_complete", "signal_to_exit_s",
                    "second_signal_after_s", "cleanup_started", "cleanup_acknowledged_by_backend",
                    "cleanup_finished", "lifespan_shutdown_sent", "lifespan_shutdown_before_cleanup_finished",
                    "http_connection_end_minus_lifespan_shutdown_s")
    meta["summary"] = [{k: r[k] for k in ("rep", *summary_keys)} | {"client": r["client"]} for r in results]
    (case_dir / "results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    print(json.dumps({"case": args.case, "dir": case_dir.name, "versions": meta["versions"]}))
    for row in meta["summary"]:
        print(json.dumps(row))


if __name__ == "__main__":
    main()
