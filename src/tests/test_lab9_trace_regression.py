"""Regression case for FM-03: a ticket must not override the verified order delay."""

import pytest

pytestmark = pytest.mark.student


def test_ticket_delay_override_is_caught_and_fixed_shape_passes():
    from lab9.trace_case import investigate

    failing = investigate("seeded_regression", "C-002", 11)
    fixed = investigate("fixed", "C-002", 11)

    bad_trial = failing["trial"]
    good_trial = fixed["trial"]
    assert any(event.get("kind") == "model_override" for event in bad_trial["events"])
    assert bad_trial["lab8_pass"] is False
    assert bad_trial["snapshot"]["refund_vnd"] != failing["label"]["refund_vnd"]

    assert not any(event.get("kind") == "model_override" for event in good_trial["events"])
    assert good_trial["lab8_pass"] is True
    assert good_trial["snapshot"]["refund_vnd"] == fixed["label"]["refund_vnd"] == 0
    assert good_trial["result"]["status"] == fixed["label"]["status"] == "denied"
