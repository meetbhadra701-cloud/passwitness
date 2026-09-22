import os
import json
import shutil
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
    assert localized.localization["flow_fidelity"]["status"] == "PASS"
    assert localized.localization["witness_replay"]["status"] == "CONFIRMED"
    assert localized.tool["source_revision_verified"] is False
    assert localized.tool["executable_sha256"]
    assert injected.status is Verdict.FAIL
    assert injected.localization["status"] == "LOCALIZED"
    assert injected.localization["first_divergent_stage"] == "injected_constant"
    assert injected.localization["witness_replay"]["status"] == "CONFIRMED"

    wide = analyze(
        rtl=root / "fixtures/injected_fault_wide/source.v",
        top="wide_correct",
        flow=root / "fixtures/injected_fault_wide/synthesis.ys",
        output_dir=output_root / "injected-wide",
        yosys=yosys,
        localize=True,
        timeout=120,
    )
    final = analyze(
        rtl=root / "fixtures/injected_fault_final/source.v",
        top="final_correct",
        flow=root / "fixtures/injected_fault_final/synthesis.ys",
        output_dir=output_root / "injected-final",
        yosys=yosys,
        localize=True,
        timeout=120,
    )
    assert wide.localization["first_divergent_stage"] == "faulty_scale"
    assert wide.localization["witness_replay"]["status"] == "CONFIRMED"
    assert final.localization["first_divergent_stage"] == "final_fault"
    assert final.localization["witness_replay"]["status"] == "CONFIRMED"

    relocated = tmp_path / "relocated-package"
    shutil.copytree(localized.localization["portable_package"], relocated)
    relocated_result = analyze(
        rtl=relocated / "source" / "source.v",
        top="fma_impl",
        flow=relocated / "flow" / "synthesis.ys",
        output_dir=tmp_path / "relocated-output",
        yosys=yosys,
        localize=True,
        timeout=120,
    )
    assert relocated_result.status is Verdict.FAIL
    assert relocated_result.localization["first_divergent_stage"] == "arith_tree"
    assert str(root / "fixtures") not in relocated_result.rtl
    portable_result = json.loads((relocated / "result.json").read_text())
    assert portable_result["tool"]["executable"] == "<external-yosys>"

    mismatch = analyze(
        rtl=root / "fixtures/port_mismatch/source.v",
        top="top",
        flow=root / "fixtures/port_mismatch/synthesis.ys",
        output_dir=output_root / "port-mismatch",
        yosys=yosys,
    )
    assert mismatch.status is Verdict.SETUP_ERROR
