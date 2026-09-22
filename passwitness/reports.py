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
    if result.errors:
        lines += ["", "## Errors", ""]
        lines.extend(f"- {error}" for error in result.errors)
    lines += ["", "## Generated evidence", ""]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(result.paths.items()))
    path = Path(result.output_dir) / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
