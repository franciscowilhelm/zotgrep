"""
Research script: compare coverage and speed of --fulltext-source pdf vs. zotero-index.

NOT a regression test — run manually when you want empirical data on the two backends.

Usage:
    python -m research.benchmark_fulltext_sources
    python -m research.benchmark_fulltext_sources --output results.json

Each search query is run against both backends ("pdf" and "zotero-index").
Coverage = number of result items returned.
Speed    = wall-clock seconds for the full search call.

Output is written as JSON (and printed to stdout).
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Search queries to benchmark
# All share the same metadata query ("proactiv"); only the fulltext term varies.
# ---------------------------------------------------------------------------
QUERIES: List[Dict[str, str]] = [
    {"label": "proactiv / diary",            "metadata": "proactiv", "fulltext": "diary"},
    {"label": "proactiv / daily",            "metadata": "proactiv", "fulltext": "daily"},
    {"label": "proactiv / barriers",         "metadata": "proactiv", "fulltext": "barriers"},
    {"label": "proactiv / cross-lagged",     "metadata": "proactiv", "fulltext": "cross-lagged"},
    {"label": "proactiv / time perspective", "metadata": "proactiv", "fulltext": "time perspective"},
]

BACKENDS: List[str] = ["pdf", "zotero-index"]


@dataclass
class RunResult:
    label: str
    backend: str
    metadata_query: str
    fulltext_query: str
    duration_seconds: float
    match_count: int
    item_titles: List[str]
    error: Optional[str] = None


def _load_engine(backend: str):
    """Return a connected ZoteroSearchEngine configured for *backend*."""
    # Import here so the module can be imported without pyzotero installed in
    # environments that only want to inspect the source.
    from zotgrep.config import get_config
    from zotgrep.search_engine import ZoteroSearchEngine

    config = get_config()
    config.fulltext_source = backend
    # Use the default metadata search mode (titleCreatorYear).
    engine = ZoteroSearchEngine(config)
    if not engine.connect_to_zotero():
        raise RuntimeError("Could not connect to local Zotero API.")
    return engine


def run_query(engine, query: Dict[str, str], backend: str) -> RunResult:
    """Run one (metadata, fulltext) pair and return a RunResult."""
    label        = query["label"]
    metadata_q   = query["metadata"]
    fulltext_q   = query["fulltext"]

    t0 = time.perf_counter()
    try:
        results = engine.search_zotero_and_full_text(
            metadata_q,
            fulltext_q,
            include_abstract=False,
            verbose=False,
        )
        elapsed = time.perf_counter() - t0
        titles = [r.get("title", "") for r in results]
        return RunResult(
            label=label,
            backend=backend,
            metadata_query=metadata_q,
            fulltext_query=fulltext_q,
            duration_seconds=round(elapsed, 3),
            match_count=len(results),
            item_titles=titles,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return RunResult(
            label=label,
            backend=backend,
            metadata_query=metadata_q,
            fulltext_query=fulltext_q,
            duration_seconds=round(elapsed, 3),
            match_count=0,
            item_titles=[],
            error=str(exc),
        )


def build_comparison(pdf_run: RunResult, index_run: RunResult) -> Dict[str, Any]:
    """Build a per-query comparison block."""
    pdf_set   = set(pdf_run.item_titles)
    index_set = set(index_run.item_titles)
    only_pdf   = sorted(pdf_set - index_set)
    only_index = sorted(index_set - pdf_set)
    shared     = sorted(pdf_set & index_set)

    return {
        "label":          pdf_run.label,
        "metadata_query": pdf_run.metadata_query,
        "fulltext_query": pdf_run.fulltext_query,
        "pdf": {
            "match_count":      pdf_run.match_count,
            "duration_seconds": pdf_run.duration_seconds,
            "error":            pdf_run.error,
        },
        "zotero_index": {
            "match_count":      index_run.match_count,
            "duration_seconds": index_run.duration_seconds,
            "error":            index_run.error,
        },
        "coverage_diff": {
            "only_in_pdf":         only_pdf,
            "only_in_zotero_index": only_index,
            "shared":              shared,
            "pdf_unique_count":    len(only_pdf),
            "index_unique_count":  len(only_index),
            "shared_count":        len(shared),
        },
        "speed_diff": {
            "faster_backend": (
                "pdf"
                if pdf_run.duration_seconds <= index_run.duration_seconds
                else "zotero-index"
            ),
            "speedup_seconds": round(
                abs(pdf_run.duration_seconds - index_run.duration_seconds), 3
            ),
        },
    }


def run_benchmark(output_path: Optional[Path] = None) -> Dict[str, Any]:
    print("=" * 60)
    print("ZotGrep fulltext-source benchmark")
    print("=" * 60)

    # We reuse one engine per backend to avoid repeated connection overhead.
    engines: Dict[str, Any] = {}
    for backend in BACKENDS:
        print(f"\nConnecting engine for backend: {backend} …")
        engines[backend] = _load_engine(backend)

    run_map: Dict[str, Dict[str, RunResult]] = {q["label"]: {} for q in QUERIES}

    for backend in BACKENDS:
        engine = engines[backend]
        for query in QUERIES:
            label = query["label"]
            print(f"\n[{backend}] {label}")
            result = run_query(engine, query, backend)
            run_map[label][backend] = result
            status = f"  -> {result.match_count} match(es) in {result.duration_seconds}s"
            if result.error:
                status += f"  ERROR: {result.error}"
            print(status)

    comparisons = [
        build_comparison(run_map[q["label"]]["pdf"], run_map[q["label"]]["zotero-index"])
        for q in QUERIES
    ]

    # Aggregate summary
    total_pdf_time   = sum(r["pdf"]["duration_seconds"]          for r in comparisons)
    total_index_time = sum(r["zotero_index"]["duration_seconds"] for r in comparisons)

    output: Dict[str, Any] = {
        "benchmark": {
            "backends_compared": BACKENDS,
            "query_count": len(QUERIES),
            "totals": {
                "pdf_total_seconds":         round(total_pdf_time, 3),
                "zotero_index_total_seconds": round(total_index_time, 3),
                "overall_faster_backend": (
                    "pdf" if total_pdf_time <= total_index_time else "zotero-index"
                ),
            },
        },
        "queries": comparisons,
    }

    json_output = json.dumps(output, indent=2)
    print("\n" + "=" * 60)
    print("RESULTS (JSON)")
    print("=" * 60)
    print(json_output)

    if output_path:
        output_path.write_text(json_output, encoding="utf-8")
        print(f"\nResults saved to: {output_path}")

    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark pdf vs. zotero-index fulltext sources."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write JSON results (optional; results are always printed to stdout).",
    )
    args = parser.parse_args()

    try:
        run_benchmark(output_path=args.output)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
