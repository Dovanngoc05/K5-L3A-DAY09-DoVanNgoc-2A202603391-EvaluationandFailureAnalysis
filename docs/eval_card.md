# Eval card — LogiX-VN refund agent

## Baseline v1 (M4)

- **Run ID / eval-set SHA:** `E-swarm-20261117-579b` / `579b50b33a7f` (`src/reports/baseline_v1.json`).
- **Version:** Lab 9 metric spec 1.0; eval set v1 (14 items × 5 seeds: 11, 22, 33, 44, 55); MockLLM. Use the report's manifest for exact Python version and SHA.
- **Metrics and gates:** see `config/metric_spec.yaml`. Blocking safety floors: `approval_bypass=0`, `secret_leak=0`; capability floors: refund/proposal correctness ≥0.95, reply/ledger match =1.0, pass_rate ≥0.85; pass_rate and refund correctness also require no statistically significant drop.
- **Baseline metrics:** `approval_bypass=0`, `secret_leak=0`, `db_fact_kept=0.9857`, `refund_amount_correct=0.9857`, `proposal_amount_correct=0.9857`, `reply_amount_matches_ledger=0.0`, `pass_rate=0.9857`, `pass_5=0.9286`, `cost_per_success=49.567`.
- **Fixed candidate:** `E-fixed-20261117-579b`, same eval SHA. `src/reports/eval_fixed.json` reports all safety/correctness/pass metrics at their maximum (`approval_bypass=0`, `secret_leak=0`, other rates `1.0`), `cost_per_success=48.7157`; gate exited 0 (`merge`).
- **Seeded regression:** `src/reports/eval_seeded_regression.json` was generated. The reported gate output was `exit 1 — blocked: approval_bypass, refund_amount_correct, proposal_amount_correct, reply_amount_matches_ledger, pass_rate`; this confirms the expected negative control because `pass_rate` is explicitly blocked. The other blocking metrics are also listed, so the seeded variant violates several v1 gates, not only the outcome floor. The run ID and exact metrics should be read from the generated report when recording final evidence.
- **Baseline caveat:** baseline `reply_amount_matches_ledger=0.0` violates the metric's 1.0 floor. Preserve the observed result and investigate the baseline behavior; the fixed candidate demonstrates the grader/gate catches and clears it.
- **Judge calibration:** tone_ok κ=0.757, precision=0.857, recall=0.800 (meets floors, supervised use only). helpful κ=0.375, precision=1.000, recall=0.300 (fails; excluded from automatic scoring). Details and disagreements: `docs/judge_audit.md`.
- **Trace case:** `docs/trace_case.md`; FM-03 ticket data overriding verified order data. Regression test: `tests/test_lab9_trace_regression.py`.
- **Gate owner:** evaluation owner maintains baseline and reviews blocked gates; a waiver requires maintainer approval and a reason recorded in the PR.
- **Pilot scope:** public, synthetic LogiX-VN refund claims against the mock order, policy, approval and ledger systems. No real customer or payment data.
- **Limitations:** MockLLM and 14 v1 items × 5 seeds; public judge replay; no real-user study or independent held-out judge set. Confidence intervals are wide at this sample size.
- **Versioning:** add or relabel eval items only in a new eval-set version; update the SHA and rerun baseline. Tighten same-version thresholds only; a looser threshold requires a new spec version and documented rationale.

## Existing v2 evidence (Advanced/Expert)

- Baseline `E-swarm-20261117-1733`, eval-set SHA `1733364a7117`, 28 items × 5 seeds, MockLLM, Python 3.14.8.
- Candidate `E-slice_regression-20261117-1733` was blocked on `slice:money_movement/pass_rate`; details: `src/reports/eval_slice_regression_v2.json` and `src/config/metric_spec_v2.yaml`.
- The verified M6 outputs supplied by the team show zero A/A deltas across metrics. Mutation scorecard: 3/3 scenarios detected, 0 false alarms. These v2 results do not substitute for the missing v1 M4 reports.
