from passwitness.models import Verdict
from passwitness.runner import analyze


def test_missing_tool_is_setup_error_and_writes_reports(tmp_path):
    result = analyze(
        rtl=tmp_path / "missing.v",
        top="top",
        flow=tmp_path / "missing.ys",
        output_dir=tmp_path / "out",
        yosys=str(tmp_path / "no-such-yosys"),
    )
    assert result.status is Verdict.SETUP_ERROR
    assert (tmp_path / "out" / "result.json").is_file()
    assert (tmp_path / "out" / "report.md").is_file()


def test_malformed_parameter_is_setup_error(tmp_path):
    result = analyze(
        rtl=tmp_path / "missing.v",
        top="top",
        flow=tmp_path / "missing.ys",
        output_dir=tmp_path / "out",
        parameters=["not-a-parameter"],
    )
    assert result.status is Verdict.SETUP_ERROR
