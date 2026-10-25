"""pytest plugin (CHK-only): apply a PY-8 candidate from candidates.py before the tests run.

PY8_CANDIDATE names the candidate; the backend comes from TORTOISE_TEST_DB's scheme.
Every process that loads the plugin (the controller and each xdist worker) writes a marker
file naming its pid, the candidate, and whether commit() is wrapped.
"""
import os
import sys

sys.path.insert(0, os.environ["PY8_EVIDENCE"])
import candidates  # noqa: E402

_scheme = os.environ.get("TORTOISE_TEST_DB", "sqlite://").split(":", 1)[0]
_backend = {"asyncpg": "asyncpg", "psycopg": "psycopg"}.get(_scheme, "sqlite")
_candidate = os.environ["PY8_CANDIDATE"]
_summary = candidates.apply(_candidate, _backend)
cls, _ = candidates._wrapper_class(_backend)
with open(os.path.join(os.environ["PY8_MARKERS"], f"marker-{os.getpid()}"), "w") as fh:
    fh.write(f"{_summary}; commit wrapped: {hasattr(cls.commit, '__wrapped__')}\n")
