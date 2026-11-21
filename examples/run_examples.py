"""Generate all example outputs for the README and RESULTS.md.

Runs the full pipeline on both shipped scenarios (30 days each,
seed 42) and prints a compact summary. Re-run after any change to
the simulator or the pipeline, then copy the printed numbers into
``examples/RESULTS.md`` — never type numbers by hand.

Usage:  python examples/run_examples.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from water_quality.pipeline import run_pipeline  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    scenarios = [
        ("normal", os.path.join(BASE, "..", "scenarios", "normal_river.json")),
        ("event", os.path.join(BASE, "..", "scenarios", "event_river.json")),
    ]
    results = {}
    for name, network_path in scenarios:
        out_dir = os.path.join(BASE, "output", name)
        summary = run_pipeline(network_path, n_days=30, seed=42,
                               out_dir=out_dir)
        results[name] = summary
        print(f"== {name} ==")
        print(f"  river: {summary['river']}, days: {summary['n_days']}, seed: 42")
        for sid, st in summary["stations"].items():
            print(f"  {sid}: mean NSF {st['mean_nsf_wqi']}, "
                  f"min NSF {st['min_nsf_wqi']}, "
                  f"mean CCME {st['mean_ccme_wqi']}, "
                  f"min CCME {st['min_ccme_wqi']}, alerts {st['n_alerts']}, "
                  f"last class {st['last_water_class']}, "
                  f"missing {st['n_missing']}/{st['n_readings']}")
        print(f"  alerts total: {summary['alerts']['total']} "
              f"{summary['alerts']['by_max_level']} "
              f"{summary['alerts']['by_parameter']}")
    combined = os.path.join(BASE, "output", "examples_summary.json")
    with open(combined, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"wrote {combined}")


if __name__ == "__main__":
    main()
