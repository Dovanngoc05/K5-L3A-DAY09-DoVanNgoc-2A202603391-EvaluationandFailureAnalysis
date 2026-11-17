"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    def finite_values(value: Any, path: str) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                problems.append(f"{path}: non-finite value {value}")
        elif isinstance(value, dict):
            for key, nested in value.items():
                finite_values(nested, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, nested in enumerate(value):
                finite_values(nested, f"{path}[{index}]")

    report_metrics = pr.get("metrics")
    if not isinstance(report_metrics, dict):
        problems.append("metrics is missing or is not an object")
        report_metrics = {}
    finite_values(report_metrics, "metrics")
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures is non-empty ({len(pr['evaluator_failures'])})")

    rows = pr.get("rows")
    if not isinstance(rows, list):
        problems.append("rows is missing or is not a list")
        rows = []
    manifest = pr.get("manifest") or {}
    try:
        expected_rows = int(manifest["items"]) * len(manifest["seeds"])
        if len(rows) != expected_rows:
            problems.append(f"row count {len(rows)} != manifest items × seeds ({expected_rows})")
    except (KeyError, TypeError, ValueError):
        problems.append("manifest must include integer items and a seeds list")

    def row_keys(report: dict, report_name: str) -> tuple[list[tuple[Any, Any]], set[tuple[Any, Any]]]:
        report_rows = report.get("rows")
        if not isinstance(report_rows, list):
            problems.append(f"{report_name} rows is missing or is not a list")
            return [], set()
        keys = []
        for index, row in enumerate(report_rows):
            if not isinstance(row, dict) or "item_id" not in row or "seed" not in row:
                problems.append(f"{report_name} row {index} missing item_id or seed")
                continue
            keys.append((row["item_id"], row["seed"]))
        key_set = set(keys)
        if len(key_set) != len(keys):
            problems.append(f"{report_name} contains duplicate (item_id, seed) rows")
        return keys, key_set

    _, pr_set = row_keys(pr, "PR")
    _, base_set = row_keys(base, "baseline")
    if pr_set != base_set:
        missing = sorted(base_set - pr_set, key=str)
        extra = sorted(pr_set - base_set, key=str)
        if missing:
            problems.append(f"PR is missing baseline (item_id, seed) rows: {missing[:5]}")
        if extra:
            problems.append(f"PR has extra (item_id, seed) rows: {extra[:5]}")

    # Metrics emitted per trial must be present and non-null on every row. Summary metrics
    # (for example pass_hat_5 and cost_per_success) are produced only in report["metrics"].
    row_metrics = [m["id"] for m in spec.get("metrics", [])
                   if m.get("grader") != "lab8.metrics.summarize" and m.get("id")]
    summary_metrics = [m["id"] for m in spec.get("metrics", [])
                       if m.get("grader") == "lab8.metrics.summarize" and m.get("id")]
    for metric in summary_metrics:
        if metric not in report_metrics or report_metrics[metric] is None:
            problems.append(f"PR summary metric {metric} is missing")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"PR row {index} is not an object")
            continue
        finite_values(row, f"rows[{index}]")
        for metric in row_metrics:
            if metric not in row or row[metric] is None:
                problems.append(f"PR row {index} ({row.get('item_id')}@{row.get('seed')}): missing {metric}")

    # Slice membership must be stable for each item across seeds and between PR and baseline.
    def slices_by_item(report_rows: list, report_name: str) -> dict[Any, tuple[str, ...]]:
        found: dict[Any, tuple[str, ...]] = {}
        for index, row in enumerate(report_rows):
            if not isinstance(row, dict) or "item_id" not in row:
                continue
            tags = row.get("slices") or []
            if not isinstance(tags, (list, tuple, set)):
                problems.append(f"{report_name} row {index}: slices is not a list")
                continue
            normalized = tuple(sorted({str(tag) for tag in tags}))
            item_id = row["item_id"]
            if item_id in found and found[item_id] != normalized:
                problems.append(f"{report_name} item {item_id}: slice tags vary across seeds")
            found[item_id] = normalized
        return found

    pr_slices = slices_by_item(rows, "PR")
    base_rows = base.get("rows") if isinstance(base.get("rows"), list) else []
    base_slices = slices_by_item(base_rows, "baseline")
    for item_id in sorted(set(pr_slices) | set(base_slices), key=str):
        if pr_slices.get(item_id) != base_slices.get(item_id):
            problems.append(
                f"item {item_id}: PR slice tags {pr_slices.get(item_id, ())} "
                f"differ from baseline {base_slices.get(item_id, ())}"
            )

    # Ratchet policy applies only when both specs describe the same eval-set version.
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def compare_thresholds(current: dict, previous: dict, label: str) -> None:
            for key in ("max", "max_increase"):
                if key in previous and (key not in current or current[key] > previous[key]):
                    problems.append(f"{label}: threshold {key} loosened or removed")
            if "min" in previous and ("min" not in current or current["min"] < previous["min"]):
                problems.append(f"{label}: threshold min loosened or removed")
            if previous.get("no_significant_drop") and not current.get("no_significant_drop"):
                problems.append(f"{label}: no_significant_drop was removed")

        def ratchet_entries(current_entries: list, previous_entries: list, section: str,
                            key_fields: tuple[str, ...]) -> None:
            current_by_key = {tuple(entry.get(k) for k in key_fields): entry for entry in current_entries}
            previous_by_key = {tuple(entry.get(k) for k in key_fields): entry for entry in previous_entries}
            for key, previous in previous_by_key.items():
                current = current_by_key.get(key)
                label = f"{section} {key}"
                if current is None:
                    problems.append(f"{label}: entry disappeared from spec")
                    continue
                compare_thresholds(current.get("threshold", current),
                                   previous.get("threshold", previous), label)
                if previous.get("blocking") and not current.get("blocking"):
                    problems.append(f"{label}: blocking changed from true to false")

        ratchet_entries(spec.get("metrics", []), base_spec.get("metrics", []),
                        "metric", ("id",))
        ratchet_entries(spec.get("slices", []), base_spec.get("slices", []),
                        "slice", ("name", "metric"))

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})

    for slice_spec in spec.get("slices", []):
        name = slice_spec["name"]
        metric = slice_spec["metric"]
        slice_id = f"slice:{name}/{metric}"
        pr_values = per_item(pr, metric, slice_name=name)
        base_values = per_item(base, metric, slice_name=name)
        threshold = slice_spec.get("min")
        no_drop = bool(slice_spec.get("no_significant_drop", False))

        if not pr_values:
            verdict = "missing"
            value = None
            note = "no PR observations in slice"
        else:
            value = sum(pr_values.values()) / len(pr_values)
            failed = threshold is not None and value < threshold
            note = ""

            if no_drop:
                keys = sorted(set(pr_values) & set(base_values))
                if not keys:
                    failed = True
                    note = "no paired PR/baseline items in slice"
                else:
                    delta, lo, hi = stats.paired_bootstrap(
                        [pr_values[k] for k in keys],
                        [base_values[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    ci_note = f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    note = f"{note}; {ci_note}" if note else ci_note
                    if hi < 0:
                        failed = True

            verdict = "fail" if failed else "ok"

        label = "BLOCK" if verdict != "ok" and slice_spec.get("blocking", False) else (
            "warn" if verdict != "ok" else "ok")
        if verdict != "ok" and slice_spec.get("blocking", False):
            blocked.append(slice_id)
        lines.append(
            f"  {slice_id:<36} {value!s:<8} {json.dumps(slice_spec, ensure_ascii=False):<60} "
            f"{note:<36} {label}"
        )

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
