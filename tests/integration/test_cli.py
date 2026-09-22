import os
import uuid
from pathlib import Path

import pytest

from passwitness.models import Verdict
from passwitness.runner import analyze


@pytest.mark.integration
def test_correct_and_incorrect_controls(tmp_path):
    yosys = os.environ.get("PASSWITNESS_YOSYS")
    if not yosys:
        pytest.skip("set PASSWITNESS_YOSYS to run the Yosys integration test")
    root = Path(__file__).parents[2]
    output_root = root / "test-output" / uuid.uuid4().hex
    correct = analyze(
        rtl=root / "fixtures/correct_arithmetic/source.v",
        top="correct_arithmetic",
        flow=root / "fixtures/correct_arithmetic/synthesis.ys",
        output_dir=output_root / "correct",
        yosys=yosys,
    )
    incorrect = analyze(
        rtl=root / "fixtures/incorrect_arithmetic/source.v",
        top="correct_arithmetic",
        flow=root / "fixtures/incorrect_arithmetic/synthesis.ys",
        output_dir=output_root / "incorrect",
        yosys=yosys,
    )
    assert correct.status is Verdict.PASS
    assert incorrect.status is Verdict.FAIL


@pytest.mark.integration
def test_real_signed_fma_localization_and_injected_fault(tmp_path):
    yosys = os.environ.get("PASSWITNESS_YOSYS")
    if not yosys:
        pytest.skip("set PASSWITNESS_YOSYS to run the Yosys integration test")
    root = Path(__file__).parents[2]
    output_root = root / "test-output" / uuid.uuid4().hex
    localized = analyze(
        rtl=root / "fixtures/signed_fma_bug/source.v",
        top="fma_impl",
        flow=root / "fixtures/signed_fma_bug/synthesis.ys",
        output_dir=output_root / "signed-fma",
        yosys=yosys,
        localize=True,
        timeout=120,
    )
    injected = analyze(
        rtl=root / "fixtures/injected_fault/source.v",
        top="correct_arithmetic",
        flow=root / "fixtures/injected_fault/synthesis.ys",
        output_dir=output_root / "injected-fault",
        yosys=yosys,
        localize=True,
        timeout=120,
    )
    assert localized.status is Verdict.FAIL
    assert localized.localization["status"] == "LOCALIZED"
    assert localized.localization["first_divergent_stage"] == "arith_tree"
    assert localized.localization["checkpoints"][4]["verdict"] == "PASS"
    assert localized.localization["checkpoints"][5]["verdict"] == "FAIL"
    assert Path(localized.localization["portable_package"]).is_dir()
    assert injected.status is Verdict.FAIL
    assert injected.localization["status"] == "LOCALIZED"
    assert injected.localization["first_divergent_stage"] == "injected_constant"
