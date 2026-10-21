"""Control flow for the production-reachability cases.

A harness PASS means the independent evidence is complete. The research summary
classifies the framework contract separately.
"""

from __future__ import annotations

from typing import Any, Callable


def run_pr(
    kind: str,
    message: dict[str, Any],
    checkpoint: Callable[..., Any],
    *,
    boundary: Callable[[Callable[[Any], None]], dict[str, Any]],
    write: Callable[[Any, str], None],
    insert_taken: Callable[[Any], None],
    identify: Callable[[Any], dict[str, Any]],
    reuse: Callable[[str, Callable[..., Any]], dict[str, Any]],
    err_info: Callable[[BaseException], dict[str, Any]],
    is_protocol: Callable[[BaseException], bool],
    savepoint: Callable[[Any], dict[str, Any]] | None = None,
    probe: Callable[[], dict[str, Any]] | None = None,
    hooks: Callable[[], dict[str, Any]] | None = None,
    on_start: Callable[[Any], None] | None = None,
    form: str | None = None,
) -> dict[str, Any]:
    markers = message["markers"]
    steps: dict[str, Any] = {"variant": kind}
    pid: dict[str, int | None] = {"v": None}

    def work(handle: Any) -> None:
        if on_start is not None:
            on_start(handle)
        write(handle, markers["tx"])
        ident = identify(handle)
        pid["v"] = ident["pid"]
        checkpoint("after-write", ident)
        if kind == "control":
            try:
                insert_taken(handle)
            except Exception as exc:
                if is_protocol(exc):
                    raise
                steps["violation"] = err_info(exc)
                raise
            raise RuntimeError("the duplicate insert did not raise")
        if kind == "savepoint":
            if savepoint is None:
                raise RuntimeError("savepoint API was not provided")
            try:
                steps["savepoint"] = savepoint(handle)
            except Exception as exc:
                if is_protocol(exc):
                    raise
                info = err_info(exc)
                steps["savepoint"] = {"recovered": False, "error": info}
                steps["violation"] = info
                checkpoint("before-end", {"pid": pid["v"]})
                raise
            steps["violation"] = (steps.get("savepoint") or {}).get("violation")
            code = (steps["violation"] or {}).get("code")
            if code != "23505":
                raise RuntimeError(f"the savepoint statement did not raise 23505 ({code})")
        else:
            try:
                insert_taken(handle)
            except Exception as exc:
                if is_protocol(exc):
                    raise
                steps["violation"] = err_info(exc)
            else:
                raise RuntimeError("the duplicate insert did not raise")
        checkpoint("before-end", {"pid": pid["v"]})

    outcome = dict(boundary(work))
    checkpoint("after-api", {"pid": pid["v"]} if pid["v"] is not None else {})
    if probe is None:
        steps["probe"] = {"supported": False}
    else:
        try:
            steps["probe"] = probe()
        except Exception as exc:
            if is_protocol(exc):
                raise
            steps["probe"] = {"supported": True, "ok": False, "error": err_info(exc)}
    steps["hooks"] = hooks() if hooks is not None else {"supported": False}
    steps["reuse"] = reuse(markers["reuse"], checkpoint)
    reuse_pid = steps["reuse"].get("pid") if isinstance(steps["reuse"], dict) else None
    if isinstance(steps["reuse"], dict):
        steps["reuse"]["same_backend"] = None if pid["v"] is None or reuse_pid is None else reuse_pid == pid["v"]
    outcome["steps"] = {**(outcome.get("steps") or {}), **steps}
    if form:
        outcome["form"] = form
    return outcome
