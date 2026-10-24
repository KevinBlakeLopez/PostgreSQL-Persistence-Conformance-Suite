"""Uvicorn --timeout-graceful-shutdown: the tasks it cancels are not awaited.

A request outlives the graceful-shutdown timeout, so Uvicorn cancels it. The
request's ``finally`` needs one more awaited step (here a 0.5 s sleep standing
in for a rollback or a lock release). Uvicorn starts the lifespan shutdown at
once and, on SIGTERM, ends the process before that step finishes.

Run:  python minimal_repro.py [--sigint]
Needs: uvicorn. Prints the server's output, its exit status, and a verdict.
Exits 1 when the cleanup did not finish before the lifespan shutdown.
"""

import asyncio
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await receive()
        await send({"type": "lifespan.startup.complete"})
        await receive()
        print("app: lifespan shutdown", flush=True)
        await send({"type": "lifespan.shutdown.complete"})
        return
    try:
        print("app: request started", flush=True)
        await asyncio.Event().wait()  # outlives the graceful-shutdown timeout
    finally:
        print("app: cleanup started", flush=True)
        await asyncio.sleep(0.5)  # one more awaited step, e.g. a rollback
        print("app: cleanup finished", flush=True)


def main() -> None:
    sig = signal.SIGINT if "--sigint" in sys.argv else signal.SIGTERM
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cmd = [sys.executable, "-m", "uvicorn", "minimal_repro:app", "--app-dir", str(Path(__file__).resolve().parent),
           "--port", str(port), "--timeout-graceful-shutdown", "1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env={**os.environ, "PYTHONUNBUFFERED": "1"})
    lines: queue.Queue[str] = queue.Queue()
    output: list[str] = []
    reader = threading.Thread(target=lambda: [lines.put(line) for line in proc.stdout])
    reader.start()

    def echo(line: str) -> None:
        output.append(line)
        print(line, end="")

    def echo_until(text: str) -> None:
        while True:
            line = lines.get(timeout=15)
            echo(line)
            if text in line:
                return

    client = None
    try:
        echo_until("Uvicorn running")
        client = socket.create_connection(("127.0.0.1", port))
        client.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        echo_until("app: request started")
        proc.send_signal(sig)
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:  # a wait above failed: do not leave the server running
            proc.kill()
            proc.wait()
        reader.join(5)
        while not lines.empty():
            echo(lines.get())
        if client is not None:
            client.close()

    finished = any("app: cleanup finished" in line for line in output)
    lifespan = next((i for i, line in enumerate(output) if "app: lifespan shutdown" in line), None)
    cleanup = next((i for i, line in enumerate(output) if "app: cleanup finished" in line), None)
    in_order = finished and lifespan is not None and cleanup < lifespan
    print(f"--- sent {sig.name}; server exit status {proc.returncode}")
    print(f"--- cleanup finished: {'yes' if finished else 'NO'}; "
          f"finished before lifespan shutdown: {'yes' if in_order else 'NO'}")
    sys.exit(0 if in_order else 1)


if __name__ == "__main__":
    main()
