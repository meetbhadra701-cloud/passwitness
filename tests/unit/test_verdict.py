from passwitness.models import Verdict
from passwitness.verdict import classify_formal_log


def test_explicit_sat_success_is_pass():
    verdict, _ = classify_formal_log("SAT proof finished - no model found: SUCCESS!", 0)
    assert verdict is Verdict.PASS


def test_sat_model_is_fail_even_when_process_failed():
    log = "SAT proof finished - model found: FAIL!\n"
    verdict, _ = classify_formal_log(log, 1)
    assert verdict is Verdict.FAIL


def test_historical_false_pass_log_is_fail():
    log = """\
SAT proof finished - model found: FAIL!
Time spent: 99% 1x sat (0 sec)
"""
    verdict, _ = classify_formal_log(log, 0)
    assert verdict is Verdict.FAIL


def test_missing_marker_fails_closed():
    verdict, _ = classify_formal_log("Yosys completed without running sat.", 0)
    assert verdict is Verdict.SETUP_ERROR


def test_timeout_is_not_pass():
    verdict, _ = classify_formal_log("process still running", None, timed_out=True)
    assert verdict is Verdict.TIMEOUT


def test_error_wins_over_an_untrustworthy_log():
    verdict, _ = classify_formal_log("ERROR: failed to import candidate", 1)
    assert verdict is Verdict.SETUP_ERROR
