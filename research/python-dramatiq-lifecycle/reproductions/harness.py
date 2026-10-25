"""Observer and fault injector for the Dramatiq lifecycle experiments.

The harness owns everything the worker cannot vouch for:

* the broker: a private redis-server process with append-only persistence
  (appendfsync always), which the harness starts, stops and restarts;
* the witness: a TCP service that records every event sent by the actor and
  by the observation hooks, stamps it with the harness's clock, and holds
  barriers until the harness releases them;
* broker snapshots, read over the harness's own Redis connection.

Worker logs are kept as evidence of what Dramatiq believed. Outcomes are
decided from the snapshots and the witness record.
"""

import hashlib
import json
import os
import platform
import signal
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REDIS_SERVER = os.environ.get("PPCS_REDIS_SERVER", "/opt/homebrew/bin/redis-server")
AGGRESSIVE_MAINTENANCE = {"PPCS_HEARTBEAT_TIMEOUT_MS": "2000", "PPCS_MAINTENANCE_CHANCE": "1000000"}


class Timeline:
    """Append-only log of the harness's own actions."""

    def __init__(self, path):
        self.file = open(path, "a", buffering=1)
        self.t0 = time.monotonic()

    def log(self, event, **fields):
        record = {"t": time.time(), "dt": round(time.monotonic() - self.t0, 3), "event": event, **fields}
        self.file.write(json.dumps(record) + "\n")
        print("[%8.3f] %s %s" % (record["dt"], event, json.dumps(fields) if fields else ""), flush=True)


class RedisServer:
    def __init__(self, port, workdir, timeline):
        self.port = port
        self.dir = Path(workdir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.timeline = timeline
        self.proc = None
        self.starts = 0

    def command(self):
        return [
            REDIS_SERVER,
            "--port", str(self.port),
            "--bind", "127.0.0.1",
            "--protected-mode", "yes",
            "--dir", str(self.dir),
            "--appendonly", "yes",
            "--appendfsync", "always",
            "--save", "",
            "--daemonize", "no",
            "--logfile", str(self.dir / "redis.log"),
            "--enable-debug-command", "local",
        ]

    def client(self):
        return redis.Redis(
            host="127.0.0.1",
            port=self.port,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=2,
            retry=Retry(NoBackoff(), 0),
        )

    def start(self):
        assert self.proc is None or self.proc.poll() is not None, "redis-server already running"
        self.proc = subprocess.Popen(self.command(), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        self.starts += 1
        deadline = time.monotonic() + 20
        while True:
            try:
                if self.client().ping():
                    break
            except (redis.exceptions.ConnectionError, redis.exceptions.BusyLoadingError):
                if time.monotonic() > deadline or self.proc.poll() is not None:
                    raise
                time.sleep(0.02)
        self.timeline.log("redis_started", pid=self.proc.pid, port=self.port, start=self.starts)

    def stop(self, sig=signal.SIGTERM):
        self.timeline.log("redis_stopping", signal=sig.name)
        self.proc.send_signal(sig)
        code = self.proc.wait(timeout=30)
        self.timeline.log("redis_stopped", returncode=code)

    def running(self):
        return self.proc is not None and self.proc.poll() is None


class Witness:
    """External witness. One JSON line in, one JSON line out per connection.
    A request with "barrier": true is answered only after release()."""

    def __init__(self, port, path):
        self.file = open(path, "a", buffering=1)
        self.cond = threading.Condition()
        self.events = []
        self.pending = {}
        self.actions = {}
        witness = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                line = self.rfile.readline()
                if not line:
                    return
                payload = json.loads(line)
                with witness.cond:
                    record = {"seq": len(witness.events) + 1, "t_server": time.time(), **payload}
                    witness.events.append(record)
                    witness.file.write(json.dumps(record) + "\n")
                    witness.file.flush()
                    os.fsync(witness.file.fileno())
                    if payload.get("barrier"):
                        witness.pending[record["seq"]] = record
                    witness.cond.notify_all()
                    action = "ok"
                    if payload.get("barrier"):
                        while record["seq"] not in witness.actions:
                            witness.cond.wait()
                        action = witness.actions.pop(record["seq"])
                        del witness.pending[record["seq"]]
                self.wfile.write((json.dumps({"action": action}) + "\n").encode())

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self.server = Server(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wait_for(self, pred, timeout):
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                for event in self.events:
                    if pred(event):
                        return event
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.cond.wait(remaining)

    def select(self, pred):
        with self.cond:
            return [event for event in self.events if pred(event)]

    def release(self, pred, action):
        with self.cond:
            released = 0
            for seq, record in self.pending.items():
                if seq not in self.actions and pred(record):
                    self.actions[seq] = action
                    released += 1
            self.cond.notify_all()
        return released

    def close(self):
        with self.cond:
            for seq in self.pending:
                self.actions.setdefault(seq, "ok")
            self.cond.notify_all()
        self.server.shutdown()
        self.server.server_close()


class WorkerProc:
    """One `dramatiq` CLI invocation (main process plus one worker process),
    in its own process group."""

    def __init__(self, name, run, env, python=None, threads=1, extra_args=()):
        self.name = name
        self.run = run
        self.log_path = run.dir / ("%s.log" % name)
        self.env = {
            "PATH": "/usr/bin:/bin",
            "HOME": os.environ["HOME"],
            "PPCS_REDIS_PORT": str(run.worker_redis_port),
            "PPCS_WITNESS_PORT": str(run.witness_port),
            **env,
        }
        self.command = [
            python or run.python, "-I", "-u", "-m", "dramatiq", "app",
            "--path", str(HERE),
            "--processes", "1",
            "--threads", str(threads),
            "--verbose",
            *extra_args,
        ]
        self.proc = None

    def start(self):
        self.log = open(self.log_path, "ab")
        self.proc = subprocess.Popen(
            self.command, env=self.env, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=str(self.run.dir),
        )
        self.run.timeline.log("worker_started", worker=self.name, pid=self.proc.pid, env={k: v for k, v in self.env.items() if k.startswith("PPCS_")})

    def term(self):
        self.run.timeline.log("worker_sigterm", worker=self.name, pid=self.proc.pid)
        os.kill(self.proc.pid, signal.SIGTERM)

    def kill_group(self):
        self.run.timeline.log("worker_sigkill_group", worker=self.name, pgid=self.proc.pid)
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def wait(self, timeout):
        try:
            code = self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        self.run.timeline.log("worker_exited", worker=self.name, returncode=code)
        return code

    def group_pids(self):
        out = subprocess.run(["ps", "-o", "pid=", "-g", str(self.proc.pid)], capture_output=True, text=True).stdout
        return [int(p) for p in out.split()]

    def log_text(self):
        return self.log_path.read_text(errors="replace") if self.log_path.exists() else ""


def summarize_payload(payload):
    try:
        data = json.loads(payload)
    except ValueError:
        return {"raw": payload[:200]}
    options = data.get("options", {})
    return {
        "message_id": data.get("message_id"),
        "actor": data.get("actor_name"),
        "job_id": (data.get("args") or [None])[0],
        "queue_name": data.get("queue_name"),
        "retries": options.get("retries", 0),
        "eta": options.get("eta"),
    }


def snapshot(client, label):
    keys = {}
    for key in sorted(client.scan_iter(match="dramatiq:*", count=1000)):
        kind = client.type(key)
        if kind == "list":
            value = client.lrange(key, 0, -1)
        elif kind == "hash":
            raw = client.hgetall(key)
            value = {k: summarize_payload(v) for k, v in raw.items()} if key.endswith(".msgs") else raw
        elif kind == "set":
            value = sorted(client.smembers(key))
        elif kind == "zset":
            value = [[member, score] for member, score in client.zrange(key, 0, -1, withscores=True)]
        elif kind == "none":
            # Deleted between SCAN and TYPE (an emptied set or list).
            continue
        else:
            value = None
        keys[key] = {"type": kind, "value": value}
    return {"label": label, "t": time.time(), "now_ms": int(time.time() * 1000), "keys": keys}


def locate(snap, message_id):
    """Every place a Dramatiq message id appears: payload hashes, and the
    lists, sets and sorted sets that hold its Redis ids."""
    found = []
    for key, entry in snap["keys"].items():
        if entry["type"] == "hash" and key.endswith(".msgs"):
            for redis_id, summary in entry["value"].items():
                if summary.get("message_id") == message_id:
                    holders = []
                    for other, other_entry in snap["keys"].items():
                        if other_entry["type"] in ("list", "set") and redis_id in other_entry["value"]:
                            holders.append(other)
                        if other_entry["type"] == "zset" and redis_id in [m for m, _ in other_entry["value"]]:
                            holders.append(other)
                    found.append({"payload_hash": key, "redis_message_id": redis_id, "retries": summary.get("retries"), "held_by": holders})
    return found


def heartbeat_ages(snap):
    entry = snap["keys"].get("dramatiq:__heartbeats__")
    if not entry:
        return {}
    return {worker: snap["now_ms"] - int(score) for worker, score in entry["value"]}


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment(python, client):
    probe = (
        "import json, platform, sys, dramatiq, redis, pathlib, hashlib\n"
        "root = pathlib.Path(dramatiq.__file__).parent\n"
        "files = ['worker.py', 'brokers/redis.py', 'brokers/redis/dispatch.lua', 'middleware/retries.py', 'cli.py', 'broker.py']\n"
        "print(json.dumps({'python': sys.version.split()[0], 'dramatiq': dramatiq.__version__, 'redis_py': redis.__version__,"
        " 'dramatiq_path': str(root), 'sha256': {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files}}))\n"
    )
    versions = json.loads(subprocess.run([python, "-I", "-c", probe], capture_output=True, text=True, check=True).stdout)
    info = client.info("server")
    config = {k: v for k, v in client.config_get("append*").items() if k in ("appendonly", "appendfsync")}
    return {
        **versions,
        "dramatiq_build": os.environ.get("PPCS_DRAMATIQ_BUILD", "unrecorded"),
        "redis_server": info.get("redis_version"),
        "redis_config": config,
        "os": platform.platform(),
        "machine": platform.machine(),
    }


class Run:
    """One repetition: its own directory, broker, witness and workers."""

    def __init__(self, experiment, variant, rep, redis_port, witness_port, python=None, proxy_port=None):
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.dir = STUDY / "outputs" / os.environ.get("PPCS_OUTPUTS_SUBDIR", "") / experiment / variant / ("%s-rep%d" % (stamp, rep))
        self.dir.mkdir(parents=True, exist_ok=False)
        self.experiment, self.variant, self.rep = experiment, variant, rep
        self.redis_port, self.witness_port = redis_port, witness_port
        self.python = python or sys.executable
        self.timeline = Timeline(self.dir / "timeline.jsonl")
        self.redis = RedisServer(redis_port, self.dir / "redis", self.timeline)
        self.witness = Witness(witness_port, self.dir / "witness.jsonl")
        # With a proxy, workers reach Redis through it; the observer and the
        # producer still connect to Redis directly.
        self.proxy = None
        if proxy_port:
            from faultproxy import FaultProxy

            self.proxy = FaultProxy(proxy_port, redis_port, self.timeline)
        self.worker_redis_port = proxy_port or redis_port
        self.snapshots = open(self.dir / "snapshots.jsonl", "a", buffering=1)
        self.workers = []
        self.result = {"experiment": experiment, "variant": variant, "rep": rep, "dir": str(self.dir.relative_to(STUDY))}

    def worker(self, name, env, **kwargs):
        proc = WorkerProc(name, self, env, **kwargs)
        self.workers.append(proc)
        return proc

    def snap(self, label):
        snap = snapshot(self.redis.client(), label)
        self.snapshots.write(json.dumps(snap) + "\n")
        self.timeline.log("snapshot", label=label, keys=sorted(snap["keys"]))
        return snap

    def wait(self, pred, timeout, what):
        event = self.witness.wait_for(pred, timeout)
        self.timeline.log("waited" if event else "wait_timeout", what=what, seq=event and event["seq"])
        return event

    def finish(self):
        for proc in self.workers:
            if proc.proc is not None and proc.proc.poll() is None:
                proc.kill_group()
                proc.wait(10)
        if self.redis.running():
            self.redis.stop()
        if self.proxy:
            self.proxy.close()
        self.witness.close()
        self.result["finished_at"] = time.time()
        (self.dir / "result.json").write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
        self.timeline.log("result_written", path=str(self.dir / "result.json"))
