"""Day 6 (Member A): time each task and build the hours-saved table.

Run from the repo root:

    python -m src.graph.benchmark                 # 20 timed runs per task
    python -m src.graph.benchmark --repeats 50    # steadier numbers
    python -m src.graph.benchmark --chiller-po PO-017 --slip-days 21

Outputs (all in docs/):
    benchmark_results.json   raw timings, for the record
    hours_saved.md           the table to paste into slides / README
    hours_saved.csv          same table for Excel

Honest-scope rules (also stated inside the generated table):
  * Manual times come from docs/manual_estimates.json and are OUR estimates.
  * System times are measured here, from cached AI results (no live API calls).
  * If data/cache/timings.json exists (Member B logs the live Claude time
    for test generation), it is added to the test-package task so the
    number is not flattered by the cache.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOCS = ROOT / "docs"
ESTIMATES = DOCS / "manual_estimates.json"
TIMINGS_CACHE = ROOT / "data" / "cache" / "timings.json"

# ---------------------------------------------------------------------------
# 1. ADAPTER: the only place that knows your function names.
#    Each entry lists (module, function) candidates; the first that imports
#    wins. If your names differ, add them here. Nothing else needs editing.
# ---------------------------------------------------------------------------
CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "build_graph": [("src.graph.build_graph", "build_graph")],
    "check_deviations": [("src.graph.deviation", "all_alerts")],
    "find_untested": [("src.graph.deviation", "find_untested_clauses")],
    "load_tested_ids": [("src.graph.deviation", "load_tested_clause_ids")],
    "blast_radius": [("src.graph.blast", "blast_radius")],
    "estimate_delay": [("src.graph.blast", "simulate_delay")],
    # optional pieces owned by B and C: skipped cleanly if missing
    "export_matrix": [
        ("src.reports.traceability", "build_matrix_bytes"),
    ],
    "export_docx": [("src.reports.test_package", "build_test_package_bytes")],
    "check_photos": [
        ("src.vision.reality_delta", "check_all_photos"),
        ("src.vision.reality_delta", "run_all"),
    ],
}


def resolve(name: str):
    """Return the callable for `name`, or None if no candidate imports."""
    for module_name, func_name in CANDIDATES[name]:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        func = getattr(module, func_name, None)
        if callable(func):
            return func
    return None


# ---------------------------------------------------------------------------
# 2. Timing helpers
# ---------------------------------------------------------------------------
def time_it(fn, repeats: int) -> dict:
    """Run fn once to warm up, then `repeats` timed runs."""
    fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return {
        "median_s": statistics.median(samples),
        "min_s": min(samples),
        "max_s": max(samples),
        "runs": repeats,
    }


def fmt_duration(seconds: float) -> str:
    """Human-readable duration for the table."""
    if seconds < 0.001:
        return "under 1 ms"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


def fmt_speedup(x: float) -> str:
    """Keep the claim believable: cap huge ratios instead of printing 8-digit numbers."""
    if x >= 10_000:
        return "over 10,000x"
    return f"about {x:,.0f}x"


def fmt_hours(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f} min"
    return f"{hours:.1f} h"


# ---------------------------------------------------------------------------
# 3. The timed tasks. Each returns (callable, note) or None if not available.
# ---------------------------------------------------------------------------
def build_tasks(args):
    build_graph = resolve("build_graph")
    if build_graph is None:
        sys.exit("Could not import build_graph. Check CANDIDATES in benchmark.py.")

    graph = build_graph()  # one shared graph for the single-feature tasks
    tasks = {}

    # Task 1: spec -> test package + matrix (graph side + optional Excel)
    _find = resolve("find_untested")
    _ids = resolve("load_tested_ids")
    find_gaps = (lambda g: _find(g, _ids())) if _find and _ids else None
    export_matrix = resolve("export_matrix")
    export_docx = resolve("export_docx")

    def test_package():
        g = build_graph()  # includes loading Test nodes from tests.json
        if find_gaps:
            find_gaps(g)
        if export_matrix:
            export_matrix()
        if export_docx:
            export_docx()

    note = "from cached AI results"
    if not export_matrix:
        note += "; Excel export not found, graph + gap check only"
    tasks["test_package"] = (test_package, note)

    # Task 2: blast radius + delay estimate
    blast_radius = resolve("blast_radius")
    estimate_delay = resolve("estimate_delay")
    if blast_radius:
        def blast():
            blast_radius(graph, args.chiller_po)
            if estimate_delay:
                estimate_delay(graph, args.chiller_po, args.slip_days)

        label = "blast radius + 1,000-run delay simulation" if estimate_delay else "blast radius only"
        tasks["blast_radius"] = (blast, label)

    # Task 3: deviation check
    check_deviations = resolve("check_deviations")
    if check_deviations:
        tasks["deviation_check"] = (lambda: check_deviations(graph), "all submittals vs all clauses")

    # Task 4: photos (C's module, cached vision results). Optional.
    check_photos = resolve("check_photos")
    if check_photos:
        tasks["nameplate_check"] = (check_photos, "from cached vision results")

    return tasks


def _accepts_graph(func) -> bool:
    import inspect
    try:
        return len(inspect.signature(func).parameters) > 0
    except (TypeError, ValueError):
        return False


def live_ai_seconds() -> float:
    """Optional: Member B logs live Claude time for test generation here:
    data/cache/timings.json  ->  {"test_generation_seconds": 74.2}"""
    try:
        return float(json.loads(TIMINGS_CACHE.read_text())["test_generation_seconds"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return 0.0


# ---------------------------------------------------------------------------
# 4. Table building (pure functions: easy to test)
# ---------------------------------------------------------------------------
def build_rows(estimates: list[dict], timings: dict[str, dict]) -> list[dict]:
    rows = []
    for item in estimates:
        key = item["key"]
        if key not in timings:
            continue  # task not available: leave it out, never invent a number
        manual_h = (item["manual_hours_low"] + item["manual_hours_high"]) / 2
        system_s = timings[key]["median_s"] + timings[key].get("extra_s", 0.0)
        system_h = system_s / 3600
        rows.append({
            "key": key,
            "task": item["task"],
            "manual_low_h": item["manual_hours_low"],
            "manual_high_h": item["manual_hours_high"],
            "manual_mid_h": manual_h,
            "system_s": system_s,
            "hours_saved": max(manual_h - system_h, 0.0),
            "speedup": (manual_h * 3600) / system_s if system_s > 0 else float("inf"),
            "note": timings[key].get("note", ""),
        })
    return rows


def render_markdown(rows: list[dict], repeats: int) -> str:
    lines = [
        "# Hours saved",
        "",
        f"_Generated {datetime.now():%Y-%m-%d %H:%M}. System times are the median of "
        f"{repeats} runs on a laptop, using cached AI results._",
        "",
        "| Task | Manual (our estimate) | With our system (measured) | Hours saved | Speed-up |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        manual = (f"{fmt_hours(r['manual_low_h'])} to {fmt_hours(r['manual_high_h'])}")
        lines.append(
            f"| {r['task']} | {manual} | {fmt_duration(r['system_s'])} "
            f"| {r['hours_saved']:.1f} h | {fmt_speedup(r['speedup'])} |"
        )
    total = sum(r["hours_saved"] for r in rows)
    lines += [
        f"| **Total (one pass of each task)** | | | **{total:.1f} h** | |",
        "",
        "**Read this honestly**",
        "",
        "- Manual times are **our own estimates** (basis in `docs/manual_estimates.json`), not measured data.",
        "- Hours saved uses the midpoint of the manual range.",
        "- System times come from cached AI results. Where live Claude time was logged, it is included in the test-package row.",
        "- The nameplate check is mainly about catching errors earlier, before equipment is installed, so hours saved understates its value.",
        "",
        "**What each system time covers**",
        "",
    ]
    lines += [f"- {r['task']}: {r['note']}" for r in rows]
    return "\n".join(lines) + "\n"


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["task", "manual_low_h", "manual_high_h", "system_seconds",
                         "hours_saved", "speedup"])
        for r in rows:
            writer.writerow([r["task"], r["manual_low_h"], r["manual_high_h"],
                             f"{r['system_s']:.4f}", f"{r['hours_saved']:.2f}",
                             f"{r['speedup']:.0f}"])


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--chiller-po", default="PO-008",
                        help="ID of the planted late chiller PO (see data/expected_results.txt)")
    parser.add_argument("--slip-days", type=int, default=21)
    args = parser.parse_args(argv)

    estimates = json.loads(ESTIMATES.read_text())["tasks"]
    tasks = build_tasks(args)

    timings: dict[str, dict] = {}
    for key, (fn, note) in tasks.items():
        print(f"timing {key} ...", end=" ", flush=True)
        result = time_it(fn, args.repeats)
        result["note"] = note
        if key == "test_package":
            extra = live_ai_seconds()
            result["extra_s"] = extra
            if extra:
                result["note"] += f"; plus {fmt_duration(extra)} of live Claude time"
        timings[key] = result
        print(fmt_duration(result["median_s"] + result.get("extra_s", 0.0)))

    skipped = [e["key"] for e in estimates if e["key"] not in timings]
    if skipped:
        print("not available, left out of the table:", ", ".join(skipped))

    rows = build_rows(estimates, timings)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "benchmark_results.json").write_text(json.dumps(
        {"generated": datetime.now().isoformat(timespec="seconds"),
         "repeats": args.repeats, "timings": timings}, indent=2))
    (DOCS / "hours_saved.md").write_text(render_markdown(rows, args.repeats))
    write_csv(rows, DOCS / "hours_saved.csv")
    print("\nWrote docs/hours_saved.md, docs/hours_saved.csv, docs/benchmark_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
