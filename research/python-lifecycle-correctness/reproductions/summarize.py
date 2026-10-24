"""Print one Markdown row per recorded case from the results.json files in a run directory.

Usage: python summarize.py ../outputs/e1-run2
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path


# The default branch still reports version 0.54.0, so builds are told apart by environment name.
BUILDS = {
    "venv-313-main": "main e4981ad",
    "venv-313-fix": "main e4981ad + fix",
    "venv-313-fixb": "main e4981ad + bounded fix",
    "venv-313-std": "0.54.0 [standard]",
}


def fraction(results: list[dict], key: str) -> str:
    if any(key not in r for r in results):
        return "n/r"  # not recorded by the harness version that made this run
    return f"{sum(1 for r in results if r.get(key))}/{len(results)}"


def build_label(meta: dict, server: str) -> str:
    venv = Path(meta["argv"][meta["argv"].index("--python") + 1]).parent.parent.name
    version = BUILDS.get(venv, meta["versions"].get(server, "?"))
    return f"{server} {version}, Python {meta['versions']['python']}"


def main() -> None:
    run_dir = Path(sys.argv[1])
    print("| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for path in sorted(run_dir.glob("*/results.json")):
        data = json.loads(path.read_text())
        meta, results = data["meta"], data["results"]
        server = meta["settings"]["server"]
        server_label = build_label(meta, server)
        exit_codes = Counter(r["returncode"] for r in results)
        clients = Counter((r["client"].get("status_line") or "(no response)") for r in results if r.get("client")) or Counter({"n/a": len(results)})
        exits = [r["signal_to_exit_s"] for r in results]
        signal_label = meta["settings"]["signal"]
        if meta["settings"].get("second_signal"):
            signal_label += f" then {meta['settings']['second_signal']}"
        print(
            f"| {meta['case']} | {server_label} | {signal_label} | {len(results)} "
            f"| {fraction(results, 'observation_complete')} "
            f"| {', '.join(f'{k} ×{v}' for k, v in sorted(exit_codes.items()))} "
            f"| {fraction(results, 'hung')} | {fraction(results, 'lifespan_shutdown_sent')} "
            f"| {fraction(results, 'cleanup_started')} | {fraction(results, 'cleanup_acknowledged_by_backend')} "
            f"| {fraction(results, 'cleanup_finished')} "
            f"| {fraction(results, 'lifespan_shutdown_before_cleanup_finished')} "
            f"| {', '.join(f'{k.strip()} ×{v}' for k, v in clients.items())} "
            f"| {statistics.median(exits):.2f}, {max(exits):.2f} |"
        )


if __name__ == "__main__":
    main()
