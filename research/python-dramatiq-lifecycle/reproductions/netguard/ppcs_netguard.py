"""Test-only network guard for the Dramatiq lifecycle study.

It is loaded at interpreter start-up through ppcs_netguard.pth in the study's
virtual environments, so it also applies to Dramatiq's spawned worker
processes. TCP connections are allowed only to loopback on the study's own
ports. Anything else, for example another project's Redis on 6379, raises
PermissionError before a packet is sent. The allowlist is fixed here on
purpose: no environment variable can widen it.
"""

import socket

ALLOWED_PORTS = frozenset(range(56391, 56399))
LOOPBACK = frozenset({"127.0.0.1", "::1"})

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _check(sock, address):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    host, port = address[0], address[1]
    if host not in LOOPBACK or port not in ALLOWED_PORTS:
        raise PermissionError("ppcs_netguard: blocked connection to %r" % (address,))


def connect(self, address):
    _check(self, address)
    return _connect(self, address)


def connect_ex(self, address):
    _check(self, address)
    return _connect_ex(self, address)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
