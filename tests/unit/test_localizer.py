from passwitness.localizer import _apply_localization_guards, _localization_status, _replay_one
from passwitness.models import AnalysisResult, CheckpointRecord, FormalResult, Verdict


def records(*verdicts):
    return [
        CheckpointRecord(name=f"s{index}", index=index, transition=f"t{index}", produced=True, verdict=verdict)
        for index, verdict in enumerate(verdicts)
    ]


def test_all_pass_has_no_divergence():
    status, first, previous, interval, errors = _localization_status(records(Verdict.PASS, Verdict.PASS))
    assert (status, first, previous, interval, errors) == ("NO_DIVERGENCE", None, None, None, [])


def test_first_transformation_failure_is_inconclusive():
    status, first, previous, interval, _ = _localization_status(records(Verdict.FAIL, Verdict.FAIL))
    assert status == "INCONCLUSIVE"
    assert first is None and previous is None
    assert interval == {"start": "s0", "end": "s0"}


def test_middle_failure_is_localized():
    status, first, previous, interval, errors = _localization_status(
        records(Verdict.PASS, Verdict.PASS, Verdict.FAIL, Verdict.PASS)
    )
    assert (status, first, previous, interval, errors) == ("LOCALIZED", "t2", "s1", None, [])


def test_final_failure_is_localized():
    status, first, previous, interval, _ = _localization_status(records(Verdict.PASS, Verdict.PASS, Verdict.FAIL))
    assert (status, first, previous, interval) == ("LOCALIZED", "t2", "s1", None)


def test_timeout_before_failure_is_bounded_not_precise():
    status, first, previous, interval, _ = _localization_status(
        records(Verdict.PASS, Verdict.TIMEOUT, Verdict.FAIL)
    )
    assert status == "INCONCLUSIVE"
    assert first is None and previous is None
    assert interval == {"start": "s1", "end": "s2"}


def test_unsupported_checkpoint_cannot_localize():
    status, *_ = _localization_status(records(Verdict.PASS, Verdict.UNSUPPORTED, Verdict.FAIL))
    assert status == "UNSUPPORTED"


def test_setup_error_cannot_localize():
    status, *_ = _localization_status(records(Verdict.PASS, Verdict.SETUP_ERROR, Verdict.FAIL))
    assert status == "SETUP_ERROR"


def test_nonmonotonic_later_pass_does_not_erase_first_failure():
    status, first, previous, *_ = _localization_status(
        records(Verdict.PASS, Verdict.FAIL, Verdict.PASS, Verdict.FAIL)
    )
    assert (status, first, previous) == ("LOCALIZED", "t1", "s0")


def test_missing_checkpoint_is_setup_error():
    missing = CheckpointRecord(name="missing", index=1, transition="fault", produced=False)
    status, *_ = _localization_status([records(Verdict.PASS)[0], missing])
    assert status == "SETUP_ERROR"


def test_instrumentation_change_downgrades_localization():
    result = AnalysisResult(
        status=Verdict.FAIL,
        rtl="source.v",
        top="top",
        flow="flow.ys",
        output_dir="out",
        parameters={},
        formal=FormalResult(verdict=Verdict.FAIL),
    )
    base = {"status": "LOCALIZED", "errors": []}
    checked = _apply_localization_guards(base, result, records(Verdict.PASS, Verdict.FAIL), "FAIL")
    assert checked["status"] == "INSTRUMENTATION_MISMATCH"
    assert "functionally different" in checked["errors"][0]


def test_instrumented_final_verdict_mismatch_downgrades_localization():
    result = AnalysisResult(
        status=Verdict.PASS,
        rtl="source.v",
        top="top",
        flow="flow.ys",
        output_dir="out",
        parameters={},
        formal=FormalResult(verdict=Verdict.PASS),
    )
    base = {"status": "LOCALIZED", "errors": []}
    checked = _apply_localization_guards(base, result, records(Verdict.PASS, Verdict.FAIL), "PASS")
    assert checked["status"] == "INCONCLUSIVE"
    assert "final checkpoint verdict differs" in checked["errors"][0]


def test_instrumentation_failure_has_distinct_status():
    result = AnalysisResult(
        status=Verdict.FAIL,
        rtl="source.v",
        top="top",
        flow="flow.ys",
        output_dir="out",
        parameters={},
        formal=FormalResult(verdict=Verdict.FAIL),
    )
    base = {"status": "LOCALIZED", "errors": []}
    checked = _apply_localization_guards(base, result, records(Verdict.PASS, Verdict.FAIL), "FAIL")
    assert checked["status"] == "INSTRUMENTATION_MISMATCH"


def test_missing_fixed_witness_is_not_confirmed(tmp_path):
    class NeverCalledBackend:
        name = "fake"

    source = tmp_path / "source.v"
    source.write_text("module top(input a, output y); assign y = a; endmodule\n")
    result = _replay_one(
        backend=NeverCalledBackend(),
        rtl=source,
        candidate=source,
        candidate_kind="verilog",
        candidate_module="passwitness_candidate",
        miter=tmp_path / "miter.v",
        ports=[type("Port", (), {"name": "a", "direction": "input"})()],
        witness_model={},
        expected_mismatch=1,
        script_path=tmp_path / "replay.ys",
        log_path=tmp_path / "replay.log",
        target="failing",
    )
    assert result.status == "UNCONFIRMED"
