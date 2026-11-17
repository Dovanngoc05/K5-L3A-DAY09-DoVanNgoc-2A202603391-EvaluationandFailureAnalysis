# Trace case: ticket data overrides the verified order fact

## Trial

- **Trial:** `seeded_regression`, C-002@11; comparison: `fixed`, C-002@11.
- **Run IDs:** recorded by `python -m lab9.trace_case` at replay time; the trace runner prints each `RunResult.run_id`.
- **Failure mode:** FM-03 `ticket_trust`.

## Symptom and first wrong step

The verified order O-202 has `delay_days=2`, below the current policy's 3-day threshold, so the expected result is `denied` with no refund. The ticket claims a 5-day delay. In the failing trace, **event 3** is the first incorrect event: `model_override` with payload `{\"delay_days\": 5}` replaces the order's verified value. The subsequent quote is 20,000 VND and the seeded variant resolves the claim, while the label requires 0 VND and `denied`.

Events before the override are the normal handoff and read-only order/policy lookup; they do not change the DB facts or ledger. The override is therefore the earliest incorrect decision point. The grader also checks the returned outcome and ledger against the label.

## Fixed comparison

On `fixed`, the agent keeps the order's two-day delay, does not emit `model_override`, produces a zero quote, returns `denied`, and leaves the ledger at zero. This comparison isolates the ticket-trust behavior.

## Regression test

`tests/test_lab9_trace_regression.py::test_ticket_delay_override_is_caught_and_fixed_shape_passes` replays both trials. It asserts that the regression emits `model_override` and fails the Lab 8 grader, while `fixed` has no override, passes the grader, and leaves the ledger unchanged. Run it with:

```powershell
python -m pytest -q -m student -o addopts= tests/test_lab9_trace_regression.py
```

The test exercises the real variant and fixed shape through the normal eval task on fresh temporary SQLite stores. The trace demonstrates this seeded variant's behavior; it does not establish that every production agent would make the same mistake.

## Reproduce the trace

From `src/`:

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```
