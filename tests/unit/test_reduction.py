from pathlib import Path

import pytest

from passwitness.reduction_oracle import (
    PRESERVE_FUNCTIONAL_FAILURE,
    PRESERVE_LOCALIZED_FAILURE,
    OracleConfig,
    OracleResult,
    ReductionOracle,
)
from passwitness.reducer import find_blocks, minimize_marked_blocks, remove_block


def _analysis(tmp_path, *, status="FAIL", first="injected_constant", replay="CONFIRMED", fidelity="PASS"):
    cex = tmp_path / "cex.json"
    cex.write_text("{}", encoding="utf-8")
    return {
        "status": status,
        "formal": {"verdict": status, "counterexample_json": str(cex), "runtime_seconds": 0.1},
        "localization": {
            "status": "LOCALIZED" if first else "INCONCLUSIVE",
            "first_divergent_stage": first,
            "previous_stage": "pre_rewrite",
            "flow_fidelity": {"status": fidelity},
            "witness_replay": {"status": replay},
            "formal_check_count": 2,
            "total_runtime_seconds": 0.2,
            "checkpoints": [
                {"name": "pre_rewrite", "transition": "elaboration", "verdict": "PASS"},
                {"name": "injected", "transition": "injected_constant", "verdict": "FAIL"},
            ],
        },
    }


def test_marked_blocks_are_paired_and_removed():
    text = "module top;\n// passwitness-reduce-begin: extra\nwire a;\n// passwitness-reduce-end: extra\nendmodule\n"
    blocks = find_blocks(text)
    assert [block.name for block in blocks] == ["extra"]
    assert "wire a" not in remove_block(text, blocks[0])


def test_malformed_markers_are_setup_errors():
    with pytest.raises(ValueError):
        find_blocks("// passwitness-reduce-end: extra\n")
    with pytest.raises(ValueError):
        find_blocks("// passwitness-reduce-begin: a\n// passwitness-reduce-end: b\n")


def test_oracle_requires_real_failure_and_replay(tmp_path):
    flow = tmp_path / "flow.ys"
    flow.write_text("# flow\n", encoding="utf-8")
    source = tmp_path / "source.v"
    source.write_text("module top; endmodule\n", encoding="utf-8")
    oracle = ReductionOracle(OracleConfig("top", flow, "yosys", tmp_path / "out", PRESERVE_LOCALIZED_FAILURE, "injected_constant"))
    candidate = tmp_path / "candidate.v"
    candidate.write_text(source.read_text(), encoding="utf-8")
    accepted = oracle._evaluate_analysis(_analysis(tmp_path), "hash", candidate, tmp_path / "eval")
    assert accepted.accepted
    rejected = oracle._evaluate_analysis(_analysis(tmp_path, replay="TIMEOUT"), "hash2", candidate, tmp_path / "eval2")
    assert not rejected.accepted
    assert "replay is TIMEOUT" in rejected.reason


def test_oracle_rejects_timeout_and_wrong_localization(tmp_path):
    flow = tmp_path / "flow.ys"
    flow.write_text("# flow\n", encoding="utf-8")
    source = tmp_path / "source.v"
    source.write_text("module top; endmodule\n", encoding="utf-8")
    oracle = ReductionOracle(OracleConfig("top", flow, "yosys", tmp_path / "out", PRESERVE_LOCALIZED_FAILURE, "injected_constant"))
    result = oracle._evaluate_analysis(_analysis(tmp_path, status="TIMEOUT"), "hash", source, tmp_path / "eval")
    assert not result.accepted
    assert "not FAIL" in result.reason
    result = oracle._evaluate_analysis(_analysis(tmp_path, first="other_stage"), "hash2", source, tmp_path / "eval2")
    assert not result.accepted
    assert "expected 'injected_constant'" in result.reason


class FakeOracle:
    def __init__(self):
        self.calls = 0

    def evaluate(self, candidate, **kwargs):
        self.calls += 1
        accepted = self.calls == 1 or self.calls == 3
        return OracleResult(
            accepted=accepted,
            candidate_hash=str(self.calls),
            candidate_path=str(candidate),
            output_dir=str(candidate.parent),
            reason="accepted" if accepted else "candidate no longer fails",
            mode=PRESERVE_FUNCTIONAL_FAILURE,
            overall_verdict="FAIL" if accepted else "PASS",
            formal_checks=1,
        )


def test_marked_reducer_records_rejected_candidates(tmp_path):
    source = tmp_path / "source.v"
    source.write_text(
        "module top;\n"
        "// passwitness-reduce-begin: first\nwire a;\n// passwitness-reduce-end: first\n"
        "// passwitness-reduce-begin: second\nwire b;\n// passwitness-reduce-end: second\n"
        "endmodule\n",
        encoding="utf-8",
    )
    run = minimize_marked_blocks(
        rtl=source,
        oracle=FakeOracle(),
        work_dir=tmp_path / "work",
        max_evaluations=5,
        max_runtime=30,
    )
    assert run.status == "REDUCTION_FOUND"
    assert len(run.history) == 3
    assert any(not entry.accepted for entry in run.history[1:])
