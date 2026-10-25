"""Test-only network guard for the PY-8 Tortoise runs.

Loaded at interpreter start-up through ppcs_py8_netguard.pth, so it also applies to
pytest-xdist workers. TCP connections through Python's socket module are allowed only to
loopback on port 55497, the throwaway PostgreSQL container. Anything else, for example
another project's MySQL on 3306 or Redis on 6379, raises PermissionError before a packet
is sent. libpq (psycopg) and ODBC connect from C, so this guard does not cover them.
"""

import socket

ALLOWED_PORTS = frozenset({55497})
LOOPBACK = frozenset({"127.0.0.1", "::1"})

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _check(sock, address):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    host, port = address[0], address[1]
    if host not in LOOPBACK or port not in ALLOWED_PORTS:
        raise PermissionError("ppcs_py8_netguard: blocked connection to %r" % (address,))


def connect(self, address):
    _check(self, address)
    return _connect(self, address)


def connect_ex(self, address):
    _check(self, address)
    return _connect_ex(self, address)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
