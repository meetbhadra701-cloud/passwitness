from __future__ import annotations

import json
from pathlib import Path

from .models import AnalysisResult, Verdict


def write_result(result: AnalysisResult) -> Path:
    path = Path(result.output_dir) / "result.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_report(result: AnalysisResult) -> Path:
    lines = [
        "# PassWitness analysis report",
        "",
        f"**Verdict:** `{result.status.value}`",
        "",
        "## Verified facts",
        "",
    ]
    lines.extend(f"- {fact}" for fact in (result.verified_facts or ["No completed checks were recorded."]))
    lines += ["", "## Inferences", ""]
    lines.extend(f"- {item}" for item in (result.inferences or ["No inference was recorded."]))
    lines += ["", "## Unexecuted checks", ""]
    lines.extend(f"- {item}" for item in (result.unexecuted_checks or ["None recorded."]))
    lines += ["", "## Inputs and provenance", "", f"- RTL: `{result.rtl}`", f"- Top: `{result.top}`", f"- Flow: `{result.flow}`"]
    if result.parameters:
        lines.append(f"- Parameters: `{result.parameters}`")
    if result.tool:
        lines.append(f"- Yosys: `{result.tool.get('version', 'unknown')}`")
        if result.tool.get("commit"):
            lines.append(f"- Tool commit: `{result.tool['commit']}`")
    lines += ["", "## Formal result", "", f"- Status: `{result.formal.verdict.value}`", f"- Reason: {result.formal.reason}"]
    if result.formal.runtime_seconds is not None:
        lines.append(f"- Runtime: `{result.formal.runtime_seconds:.3f} s`")
    if result.counterexample:
        lines += ["", "### Counterexample", "", "```json", json.dumps(result.counterexample, indent=2), "```"]
    if result.localization is not None:
        localization = result.localization
        lines += ["", "## Stage localization", "", f"- Status: `{localization.get('status', 'NOT_EXECUTED')}`"]
        lines.append(f"- Mode: `{localization.get('mode', 'unknown')}`")
        if localization.get("first_divergent_stage"):
            lines.append(f"- First verified divergent transition: `{localization['first_divergent_stage']}`")
            lines.append(f"- Previous proven checkpoint: `{localization.get('previous_stage', 'unknown')}`")
        if localization.get("divergence_interval"):
            lines.append(f"- Divergence interval: `{localization['divergence_interval']}`")
        lines.append(f"- Checkpoint count: `{len(localization.get('checkpoints', []))}`")
        lines.append(f"- Formal check count: `{localization.get('formal_check_count', 0)}`")
        lines.append(f"- Synthesis runtime: `{localization.get('synthesis_runtime_seconds', 0.0):.3f} s`")
        lines.append(f"- Formal runtime: `{localization.get('formal_runtime_seconds', 0.0):.3f} s`")
        lines.append(f"- Total localization runtime: `{localization.get('total_runtime_seconds', 0.0):.3f} s`")
        first_time = localization.get("time_to_first_divergence_seconds")
        if first_time is not None:
            lines.append(f"- Time to first verified divergence: `{first_time:.3f} s`")
        checkpoints = localization.get("checkpoints", [])
        if checkpoints:
            lines += ["", "### Checkpoint results", "", "| # | Checkpoint | Transition | Produced | Proof | Snapshot |", "|---:|---|---|---|---|---|"]
            for checkpoint in checkpoints:
                snapshot = checkpoint.get("snapshot_path") or ""
                lines.append(
                    f"| {checkpoint.get('index', '')} | `{checkpoint.get('name', '')}` | `{checkpoint.get('transition', '')}` | "
                    f"`{checkpoint.get('produced', False)}` | `{checkpoint.get('verdict', 'NOT_EXECUTED')}` | `{snapshot}` |"
                )
            failing = next((item for item in checkpoints if item.get("verdict") == Verdict.FAIL.value), None)
            if failing:
                lines += ["", "### Failing-transition evidence", ""]
                lines.append(f"- Checkpoint: `{failing.get('name', '')}`")
                if failing.get("counterexample_json"):
                    lines.append(f"- Counterexample JSON: `{failing['counterexample_json']}`")
                if failing.get("counterexample_vcd"):
                    lines.append(f"- Counterexample VCD: `{failing['counterexample_vcd']}`")
                if failing.get("proof_log_path"):
                    lines.append(f"- Formal log: `{failing['proof_log_path']}`")
        if localization.get("unexecuted_stages"):
            lines.append(f"- Unexecuted stages: `{localization['unexecuted_stages']}`")
        if localization.get("errors"):
            lines += ["", "### Localization caveats", ""]
            lines.extend(f"- {error}" for error in localization["errors"])
    if result.errors:
        lines += ["", "## Errors", ""]
        lines.extend(f"- {error}" for error in result.errors)
    lines += ["", "## Generated evidence", ""]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(result.paths.items()))
    path = Path(result.output_dir) / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
