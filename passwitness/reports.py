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
        "## Investigation summary",
        "",
        f"- Final design equivalence: `{result.formal.verdict.value}`",
        f"- Formal backend: `{result.formal.backend}`",
        f"- Localization: `{(result.localization or {}).get('status', 'NOT_EXECUTED')}`",
        f"- Flow fidelity: `{(result.localization or {}).get('flow_fidelity', {}).get('status', 'NOT_EXECUTED')}`",
        f"- First verified divergent transition: `{(result.localization or {}).get('first_divergent_stage') or 'none'}`",
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
        if result.tool.get("yosys_reported_commit"):
            lines.append(f"- Yosys-reported commit: `{result.tool['yosys_reported_commit']}`")
        if result.tool.get("executable_sha256"):
            lines.append(f"- Executable SHA-256: `{result.tool['executable_sha256']}`")
        lines.append(f"- Source revision verified: `{result.tool.get('source_revision_verified', False)}`")
        if result.tool.get("verification_method"):
            lines.append(f"- Provenance method: {result.tool['verification_method']}")
    lines += ["", "## Formal result", "", f"- Status: `{result.formal.verdict.value}`", f"- Reason: {result.formal.reason}"]
    lines.append(f"- Backend: `{result.formal.backend}`")
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
        fidelity = localization.get("flow_fidelity") or {}
        if fidelity:
            lines += ["", "### Flow fidelity", "", f"- Status: `{fidelity.get('status', 'NOT_EXECUTED')}`"]
            lines.append(f"- Catalog: `{fidelity.get('catalog_id') or 'explicit flow'}`")
            lines.append(f"- Original command count: `{len(fidelity.get('original_commands', []))}`")
            lines.append(f"- Instrumented command count: `{len(fidelity.get('instrumented_commands', []))}`")
            lines.append(f"- Added checkpoint commands: `{len(fidelity.get('added_commands', []))}`")
            if fidelity.get("expanded_commands"):
                lines.append(f"- Expanded command records: `{len(fidelity['expanded_commands'])}`")
            if fidelity.get("comparison"):
                lines.append(f"- Final representation comparison: `{fidelity['comparison'].get('status', 'NOT_EXECUTED')}`")
            lines.append(f"- Original final representation: `{fidelity.get('original_final_representation')}`")
            lines.append(f"- Instrumented final representation: `{fidelity.get('instrumented_final_representation')}`")
        replay = localization.get("witness_replay") or {}
        if replay.get("status") != "NOT_EXECUTED":
            lines += ["", "### Fixed-witness replay", "", f"- Status: `{replay.get('status', 'UNCONFIRMED')}`"]
            lines.append("- Replay is explanatory evidence for one input and is not a formal proof.")
            for target, evidence in sorted((replay.get("targets") or {}).items()):
                lines.append(f"- `{target}`: `{evidence.get('status', 'UNCONFIRMED')}` — {evidence.get('reason', '')}")
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


def write_minimization_report(result: dict, path: Path) -> Path:
    """Write a reduction report with facts separated from reduction claims."""
    metrics = result.get("metrics", {})
    original = metrics.get("original", {})
    reduced = metrics.get("reduced", {})
    audit = result.get("audit", {})
    final = result.get("final_reverification", {})
    lines = [
        "# PassWitness minimization report",
        "",
        f"**Status:** `{result.get('status', 'SETUP_ERROR')}`",
        f"**Final independent verification:** `{result.get('verification_status', 'UNVERIFIED')}`",
        "",
        "## Verified facts",
        "",
        f"- Oracle mode: `{result.get('oracle_mode')}`",
        f"- Overall final candidate verdict: `{final.get('overall_verdict', 'NOT_EXECUTED')}`",
        f"- Localization: `{final.get('localization_status', 'NOT_EXECUTED')}`",
        f"- Flow fidelity: `{final.get('flow_fidelity_status', 'NOT_EXECUTED')}`",
        f"- Witness replay: `{final.get('witness_replay_status', 'NOT_EXECUTED')}`",
        f"- First divergent stage: `{final.get('first_divergent_stage') or 'none'}`",
        f"- Final candidate was independently checked in a fresh oracle directory: `{bool(final)}`",
        "",
        "## Size measurements",
        "",
        f"- Original: `{original.get('bytes', 0)} bytes`, `{original.get('lines', 0)} lines`",
        f"- Reduced: `{reduced.get('bytes', 0)} bytes`, `{reduced.get('lines', 0)} lines`",
        f"- Byte reduction: `{metrics.get('reduction_percent', {}).get('bytes', 0)}%`",
        f"- Line reduction: `{metrics.get('reduction_percent', {}).get('lines', 0)}%`",
        "",
        "## Reduction cost",
        "",
        f"- Reducer: `{result.get('reducer', {}).get('name')}` `{result.get('reducer', {}).get('version')}`",
        f"- Candidate evaluations: `{audit.get('candidate_evaluations', 0)}`",
        f"- Total candidate proposals: `{audit.get('total_candidate_proposals', 0)}`",
        f"- Unique candidate hashes: `{audit.get('unique_candidate_hashes', 0)}`",
        f"- Oracle executions: `{audit.get('oracle_executions', 0)}`",
        f"- Cache hits: `{audit.get('cache_hits', 0)}`",
        f"- Valid oracle-accepted candidates: `{audit.get('valid_oracle_accepted_candidates', 0)}`",
        f"- Unique accepted candidates: `{audit.get('unique_accepted_candidates', 0)}`",
        f"- Strict size improvements: `{audit.get('strict_size_improvements', 0)}`",
        f"- Rejected candidates: `{audit.get('rejected_candidates', 0)}`",
        f"- Formal checks: `{audit.get('formal_checks', 0)}`",
        f"- Reduction runtime: `{audit.get('reduction_runtime_seconds', 0.0):.3f} s`",
        f"- Final re-verification runtime: `{audit.get('final_reverification_runtime_seconds', 0.0):.3f} s`",
        f"- Budget exhausted: `{audit.get('budget_exhausted', False)}`",
        "",
        "## Audit trail",
        "",
        "| Candidate | Block | Oracle | Cache | Strict improvement | Accepted | Bytes | Lines | Reason |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for entry in audit.get("history", []):
        lines.append(
            f"| `{entry.get('candidate_id')}` | `{entry.get('block') or ''}` | `{entry.get('oracle_accepted')}` | `{entry.get('cache_hit')}` | "
            f"`{entry.get('strict_size_improvement')}` | `{entry.get('accepted')}` | `{entry.get('source_bytes')}` | "
            f"`{entry.get('source_lines')}` | {entry.get('reason', '')} |"
        )
    lines += ["", "## Inferences and limitations", "", "- The reduced candidate is not claimed to be globally minimal.", "- A fixed-witness replay is explanatory evidence and is not a replacement for the formal proof."]
    if result.get("reason"):
        lines.append(f"- Search result: {result['reason']}")
    if result.get("errors"):
        lines += ["", "## Errors", ""]
        lines.extend(f"- {error}" for error in result["errors"])
    lines += ["", "## Reproduction", "", f"- Portable package: `{result.get('portable_package') or 'not generated'}`"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
