from pathlib import Path

from passwitness.checkpoints import build_instrumented_flow


def test_macro_plan_is_version_gated_and_records_expansion(tmp_path):
    flow = tmp_path / "synthesis.ys"
    flow.write_text("synth -top top -arith_tree\n")
    rtl = tmp_path / "source.v"
    rtl.write_text("module top(input a, output y); assign y = a; endmodule\n")

    unsupported = build_instrumented_flow(flow, "top", tmp_path / "old", rtl, {}, tool_version="Yosys 0.58")
    assert unsupported.supported is False
    assert unsupported.mode == "unsupported_version"

    plan = build_instrumented_flow(flow, "top", tmp_path / "current", rtl, {}, tool_version="Yosys 0.69+")
    assert plan.supported is True
    assert plan.catalog_id == "yosys-0.69-synth-arith-tree"
    assert plan.original_commands == ["synth -top top -arith_tree"]
    assert plan.added_commands
    assert plan.expanded_commands[0]["original"] == plan.original_commands
    assert any(item["name"] == "arith_tree" for item in plan.execution_order)


def test_marked_flow_is_explicit_and_does_not_require_macro_expansion(tmp_path):
    flow = tmp_path / "marked.ys"
    flow.write_text("# passwitness-stage: first\nproc\n# passwitness-stage: second\nopt\n")
    rtl = tmp_path / "source.v"
    rtl.write_text("module top(input a, output y); assign y = a; endmodule\n")
    plan = build_instrumented_flow(flow, "top", tmp_path / "marked-work", rtl, {}, tool_version="Yosys 0.58")
    assert plan.supported is True
    assert plan.catalog_id == "explicit-marked-flow"
    assert [item["name"] for item in plan.execution_order if item["name"] != "load"] == ["first", "second"]
    assert not plan.expanded_commands


def test_opaque_macro_is_explicitly_unsupported(tmp_path):
    flow = tmp_path / "opaque.ys"
    flow.write_text("custom_synthesis_macro -top top\n")
    rtl = tmp_path / "source.v"
    rtl.write_text("module top(input a, output y); assign y = a; endmodule\n")
    plan = build_instrumented_flow(flow, "top", tmp_path / "opaque-work", rtl, {}, tool_version="Yosys 0.69+")
    assert plan.supported is False
    assert plan.mode == "unsupported"
    assert "exact `synth -top TOP -arith_tree`" in plan.reason


def test_marked_flow_rejects_unmarked_preamble(tmp_path):
    flow = tmp_path / "preamble.ys"
    flow.write_text("proc\n# passwitness-stage: first\nopt\n# passwitness-stage: second\ncheck\n")
    rtl = tmp_path / "source.v"
    rtl.write_text("module top(input a, output y); assign y = a; endmodule\n")
    plan = build_instrumented_flow(flow, "top", tmp_path / "preamble-work", rtl, {}, tool_version="Yosys 0.69+")
    assert plan.supported is False
