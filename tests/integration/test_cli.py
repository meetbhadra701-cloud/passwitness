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
