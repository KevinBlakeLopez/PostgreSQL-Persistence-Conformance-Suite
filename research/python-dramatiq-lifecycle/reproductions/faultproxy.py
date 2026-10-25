"""A TCP proxy between the worker and Redis that injects precise faults.

Test instrumentation for the adversarial verification. The worker connects
to the proxy; the harness's observer and producer connect to Redis directly.

* pass: forward everything unchanged.
* blackhole: stop forwarding in both directions, keeping connections open
  (a network partition). New connections are accepted and held too. When the
  blackhole ends, the held connections are closed.
* drop_reply rule: forward one matching command to Redis, then discard every
  reply on that connection and close it (Redis accepted it; the reply was
  lost).
* drop_request rule: close the connection when a matching command arrives,
  without forwarding it (Redis never received it).

Commands are matched on their decoded RESP arguments. redis-py does not
pipeline these calls, so a connection carries one outstanding command.
"""

import asyncio
import threading
import time


def parse_command(buf):
    """Parse one RESP array of bulk strings. Returns (args, consumed) or None."""
    if not buf.startswith(b"*"):
        return None
    end = buf.find(b"\r\n")
    if end < 0:
        return None
    count, pos, args = int(buf[1:end]), end + 2, []
    for _ in range(count):
        end = buf.find(b"\r\n", pos)
        if end < 0 or buf[pos:pos + 1] != b"$":
            return None
        size = int(buf[pos + 1:end])
        start = end + 2
        if len(buf) < start + size + 2:
            return None
        args.append(buf[start:start + size])
        pos = start + size + 2
    return args, pos


def dispatch_call(args):
    """(command, queue) for a Dramatiq dispatch EVALSHA/EVAL, else None.
    Layout: EVALSHA sha 1 namespace command timestamp queue worker ..."""
    if len(args) >= 7 and args[0].upper() in (b"EVALSHA", b"EVAL"):
        return args[4].decode(), args[6].decode()
    return None


class FaultProxy:
    def __init__(self, listen_port, upstream_port, timeline):
        self.listen_port, self.upstream_port, self.timeline = listen_port, upstream_port, timeline
        self.mode = "pass"
        self.rules = []
        self.held = set()
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()
        threading.Thread(target=self._run, args=(ready,), daemon=True).start()
        ready.wait(5)

    def _run(self, ready):
        asyncio.set_event_loop(self.loop)

        async def start():
            self.server = await asyncio.start_server(self._handle, "127.0.0.1", self.listen_port)

        self.loop.run_until_complete(start())
        ready.set()
        self.loop.run_forever()

    # -- control, called from the harness thread ------------------------------

    def add_rule(self, action, command, queue, count=1):
        rule = {"action": action, "command": command, "queue": queue, "remaining": count, "fired": [], "event": threading.Event()}
        self.rules.append(rule)
        self.timeline.log("proxy_rule", action=action, command=command, queue=queue, count=count)
        return rule

    def blackhole(self, seconds):
        self.mode = "blackhole"
        self.timeline.log("proxy_blackhole_start", seconds=seconds)
        time.sleep(seconds)
        self.mode = "pass"
        for writer in list(self.held):
            self.loop.call_soon_threadsafe(writer.close)
        self.timeline.log("proxy_blackhole_end", closed=len(self.held))

    def close(self):
        self.loop.call_soon_threadsafe(self.server.close)

    # -- data path ----------------------------------------------------------

    def _match(self, args):
        call = dispatch_call(args)
        if not call:
            return None
        for rule in self.rules:
            if rule["remaining"] > 0 and call == (rule["command"], rule["queue"]):
                rule["remaining"] -= 1
                rule["fired"].append(time.time())
                rule["event"].set()
                return rule
        return None

    async def _handle(self, reader, writer):
        try:
            up_reader, up_writer = await asyncio.open_connection("127.0.0.1", self.upstream_port)
        except OSError:
            writer.close()  # Redis is down: the client sees the connection close
            return
        state = {"drop_replies": False, "closed": False}

        async def shut():
            if not state["closed"]:
                state["closed"] = True
                writer.close()
                up_writer.close()
            self.held.discard(writer)

        async def client_to_server():
            buf = b""
            while not state["closed"]:
                if self.mode == "blackhole":
                    self.held.add(writer)
                    await asyncio.sleep(0.05)
                    continue
                data = await reader.read(65536)
                if not data:
                    break
                buf += data
                while True:
                    parsed = parse_command(buf)
                    if parsed is None:
                        break
                    args, used = parsed
                    raw, buf = buf[:used], buf[used:]
                    rule = self._match(args)
                    if rule and rule["action"] == "drop_request":
                        self.timeline.log("proxy_dropped_request", call=dispatch_call(args))
                        await shut()
                        return
                    if rule and rule["action"] == "drop_reply":
                        # Set before forwarding, so no reply can slip through.
                        state["drop_replies"] = True
                    up_writer.write(raw)
                    await up_writer.drain()
                    if rule and rule["action"] == "drop_reply":
                        self.timeline.log("proxy_forwarded_then_dropping_reply", call=dispatch_call(args))
                        await asyncio.sleep(0.3)  # let Redis run it
                        await shut()
                        return
                if buf and not buf.startswith(b"*"):
                    up_writer.write(buf)  # not a RESP array; pass it through
                    await up_writer.drain()
                    buf = b""
            await shut()

        async def server_to_client():
            while not state["closed"]:
                if self.mode == "blackhole":
                    await asyncio.sleep(0.05)
                    continue
                data = await up_reader.read(65536)
                if not data:
                    break
                if state["drop_replies"]:
                    continue
                writer.write(data)
                await writer.drain()
            await shut()

        try:
            await asyncio.gather(client_to_server(), server_to_client())
        except (ConnectionError, OSError):
            await shut()
