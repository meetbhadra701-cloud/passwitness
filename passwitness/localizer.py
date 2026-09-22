"""Automatic localization over real, serialized synthesis checkpoints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .checkpoints import build_instrumented_flow
from .formal import parse_model, write_miter
from .models import AnalysisResult, CheckpointRecord, Port, Verdict
from .runner import _run, _ys_path
from .verdict import classify_formal_log


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _formal_script(
    *,
    rtl: Path,
    candidate: Path,
    candidate_kind: str,
    candidate_module: str,
    miter: Path,
    top: str,
    checkpoint_json: Path,
    checkpoint_vcd: Path,
) -> str:
    lines: list[str] = []
    if candidate_kind == "rtlil":
        lines += [
            f"read_rtlil {_ys_path(candidate)}",
            f"rename {candidate_module} passwitness_candidate",
            "hierarchy -top passwitness_candidate",
            f"read_verilog -sv {_ys_path(rtl)}",
        ]
    else:
        lines += [f"read_verilog {_ys_path(candidate)}", f"read_verilog -sv {_ys_path(rtl)}"]
    lines += [
        f"read_verilog {_ys_path(miter)}",
        "hierarchy -top passwitness_miter",
        "prep -top passwitness_miter",
        "flatten",
        "opt",
        f"sat -prove mismatch 0 -verify -set-def-inputs -show-ports -dump_json {_ys_path(checkpoint_json)} -dump_vcd {_ys_path(checkpoint_vcd)}",
    ]
    return "\n".join(lines) + "\n"


def _run_proof(
    *,
    yosys: str,
    cwd: Path,
    rtl: Path,
    candidate: Path,
    candidate_kind: str,
    candidate_module: str,
    miter: Path,
    top: str,
    ports: list[Port],
    script_path: Path,
    log_path: Path,
    cex_json: Path,
    cex_vcd: Path,
    timeout: float,
) -> tuple[Verdict, str, float, dict[str, dict[str, str | int]], int | None, bool]:
    _write(
        script_path,
        _formal_script(
            rtl=rtl,
            candidate=candidate,
            candidate_kind=candidate_kind,
            candidate_module=candidate_module,
            miter=miter,
            top=top,
            checkpoint_json=cex_json,
            checkpoint_vcd=cex_vcd,
        ),
    )
    command = _run([yosys, "-s", str(script_path)], log_path, timeout, cwd)
    text = Path(command.log_path).read_text(encoding="utf-8", errors="replace")
    verdict, reason = classify_formal_log(text, command.returncode, timed_out=command.timed_out)
    model = parse_model(text)
    return verdict, reason, command.runtime_seconds or 0.0, model, command.returncode, command.timed_out


def _record_dict(record: CheckpointRecord) -> dict[str, Any]:
    return record.to_dict()


def _localization_status(records: list[CheckpointRecord]) -> tuple[str, str | None, str | None, dict[str, str] | None, list[str]]:
    if not records:
        return "INCONCLUSIVE", None, None, None, ["No checkpoint records were produced."]
    missing = [record for record in records if not record.produced]
    if missing:
        return "SETUP_ERROR", None, None, None, [f"Expected checkpoint was not produced: {record.name}" for record in missing]
    for record in records:
        if record.verdict == Verdict.UNSUPPORTED:
            return "UNSUPPORTED", None, None, None, [record.reason]
        if record.verdict == Verdict.SETUP_ERROR:
            return "SETUP_ERROR", None, None, None, [record.reason]
    for index, current in enumerate(records):
        if current.verdict != Verdict.FAIL:
            continue
        if index == 0:
            return "INCONCLUSIVE", None, None, {"start": current.name, "end": current.name}, [
                "The first checked checkpoint already failed; no verified preceding PASS exists."
            ]
        previous = records[index - 1]
        if previous.verdict == Verdict.PASS:
            prefix = records[:index]
            if all(record.verdict == Verdict.PASS for record in prefix):
                return "LOCALIZED", current.transition, previous.name, None, []
            first_uncertain = next(record for record in prefix if record.verdict != Verdict.PASS)
            return "INCONCLUSIVE", None, None, {"start": first_uncertain.name, "end": current.name}, [
                "A checkpoint before the PASS-to-FAIL pair was inconclusive."
            ]
        return "INCONCLUSIVE", None, None, {"start": previous.name, "end": current.name}, [
            "The checkpoint immediately before the failure was not proven equivalent."
        ]
    if all(record.verdict == Verdict.PASS for record in records):
        return "NO_DIVERGENCE", None, None, None, []
    first_uncertain = next((record for record in records if record.verdict != Verdict.PASS), records[-1])
    return "INCONCLUSIVE", None, None, {"start": first_uncertain.name, "end": records[-1].name}, [
        "No verified PASS-to-FAIL transition was established."
    ]


def _apply_localization_guards(
    base: dict[str, Any],
    result: AnalysisResult,
    records: list[CheckpointRecord],
    comparison_status: str,
) -> dict[str, Any]:
    """Reject localization if instrumentation changed or obscured the flow."""
    if comparison_status != Verdict.PASS.value:
        base["status"] = "INCONCLUSIVE"
        base["errors"].append(
            "The instrumented final candidate was not proven equivalent to the original Phase 1 candidate."
        )
    final_checkpoint = records[-1].verdict.value if records else Verdict.NOT_EXECUTED.value
    if result.formal.verdict.value != final_checkpoint:
        base["status"] = "INCONCLUSIVE"
        base["errors"].append("The instrumented final checkpoint verdict differs from the Phase 1 final verdict.")
    return base


def localize(
    *,
    result: AnalysisResult,
    rtl: Path,
    top: str,
    flow: Path,
    output_dir: Path,
    yosys: str,
    parameters: dict[str, str],
    timeout: float,
    ports: list[Port],
    normal_candidate: Path,
) -> dict[str, Any]:
    start = time.monotonic()
    work = output_dir / "localization"
    logs = work / "logs"
    proofs = work / "proofs"
    witnesses = work / "witnesses"
    for path in (work, logs, proofs, witnesses):
        path.mkdir(parents=True, exist_ok=True)
    plan = build_instrumented_flow(flow, top, work, rtl, parameters)
    base: dict[str, Any] = {
        "status": "NOT_EXECUTED",
        "mode": plan.mode,
        "reason": plan.reason,
        "first_divergent_stage": None,
        "previous_stage": None,
        "divergence_interval": None,
        "checkpoints": [],
        "synthesis": {},
        "flow_comparison": None,
        "formal_check_count": 0,
        "formal_runtime_seconds": 0.0,
        "synthesis_runtime_seconds": 0.0,
        "total_runtime_seconds": 0.0,
        "time_to_first_divergence_seconds": None,
        "errors": [],
        "unexecuted_stages": [],
        "instrumented_script": str(plan.script_path) if plan.script_path else None,
        "portable_package": str(output_dir / "portable") if plan.supported else None,
    }
    if not plan.supported:
        base["status"] = "UNSUPPORTED"
        base["errors"].append(plan.reason)
        base["total_runtime_seconds"] = time.monotonic() - start
        return base

    synthesis = _run([yosys, "-s", str(plan.script_path)], logs / "instrumented-synthesis.log", timeout, output_dir.parent)
    base["synthesis"] = {
        "script": str(plan.script_path),
        "log_path": synthesis.log_path,
        "returncode": synthesis.returncode,
        "runtime_seconds": synthesis.runtime_seconds,
        "commands": plan.commands or [],
    }
    base["synthesis_runtime_seconds"] = synthesis.runtime_seconds or 0.0
    if synthesis.timed_out:
        base["status"] = "INCONCLUSIVE"
        base["errors"].append("Instrumented synthesis timed out before all checkpoints were captured.")
        base["total_runtime_seconds"] = time.monotonic() - start
        return base
    if synthesis.returncode != 0:
        base["status"] = "SETUP_ERROR"
        base["errors"].append("Instrumented synthesis failed; checkpoint state is incomplete.")
        base["total_runtime_seconds"] = time.monotonic() - start
        return base

    miter = work / "checkpoint-miter.v"
    write_miter(miter, top, ports, parameters)
    records: list[CheckpointRecord] = []
    first_divergence_time: float | None = None
    for spec in plan.stages or []:
        record = CheckpointRecord(
            name=spec.name,
            index=len(records),
            transition=spec.transition,
            snapshot_path=str(spec.snapshot_path),
            produced=spec.snapshot_path.is_file(),
            capture_commands=spec.capture_commands,
            preparation_commands=[
                f"read_rtlil {spec.snapshot_path}",
                f"rename {spec.candidate_module} passwitness_candidate",
                "read_verilog -sv <golden RTL>",
                "prep -top passwitness_miter",
                "flatten",
                "opt",
            ],
        )
        if not record.produced:
            record.reason = "The expected RTLIL snapshot was not produced by the instrumented flow."
            records.append(record)
            continue
        stem = f"{record.index:03d}_{record.name}"
        try:
            (
                record.verdict,
                record.reason,
                record.proof_runtime_seconds,
                record.model,
                _,
                _,
            ) = _run_proof(
                yosys=yosys,
                cwd=output_dir.parent,
                rtl=rtl,
                candidate=spec.snapshot_path,
                candidate_kind="rtlil",
                candidate_module=spec.candidate_module,
                miter=miter,
                top=top,
                ports=ports,
                script_path=proofs / f"{stem}.ys",
                log_path=logs / f"{stem}.log",
                cex_json=witnesses / f"{stem}.json",
                cex_vcd=witnesses / f"{stem}.vcd",
                timeout=timeout,
            )
            record.proof_script_path = str(proofs / f"{stem}.ys")
            record.proof_log_path = str(logs / f"{stem}.log")
            record.counterexample_json = str(witnesses / f"{stem}.json") if (witnesses / f"{stem}.json").is_file() else None
            record.counterexample_vcd = str(witnesses / f"{stem}.vcd") if (witnesses / f"{stem}.vcd").is_file() else None
        except OSError as exc:
            record.verdict = Verdict.SETUP_ERROR
            record.reason = f"Could not start checkpoint formal proof: {exc}"
        records.append(record)
        base["formal_check_count"] += 1
        base["formal_runtime_seconds"] += record.proof_runtime_seconds or 0.0
        if first_divergence_time is None and len(records) >= 2 and records[-2].verdict == Verdict.PASS and record.verdict == Verdict.FAIL:
            first_divergence_time = time.monotonic() - start

    base["checkpoints"] = [_record_dict(record) for record in records]

    comparison: dict[str, Any] = {"status": "NOT_EXECUTED", "reason": "Instrumented-flow comparison was not executed."}
    if plan.final_snapshot and plan.final_snapshot.is_file() and normal_candidate.is_file():
        compare_miter = work / "final-flow-comparison-miter.v"
        write_miter(
            compare_miter,
            top,
            ports,
            parameters,
            reference_module="passwitness_reference",
            candidate_module="passwitness_candidate",
        )
        compare_json = witnesses / "final-flow-comparison.json"
        compare_vcd = witnesses / "final-flow-comparison.vcd"
        compare_script = proofs / "final-flow-comparison.ys"
        compare_log = logs / "final-flow-comparison.log"
        # The comparison has two candidate representations, so its script is
        # written directly rather than routed through the golden-RTL helper.
        script = "\n".join([
            f"read_verilog {_ys_path(normal_candidate)}",
            "rename passwitness_candidate passwitness_reference",
            f"read_rtlil {_ys_path(plan.final_snapshot)}",
            f"rename {top} passwitness_candidate",
            f"read_verilog {_ys_path(compare_miter)}",
            "hierarchy -top passwitness_miter",
            "prep -top passwitness_miter",
            "flatten",
            "opt",
            f"sat -prove mismatch 0 -verify -set-def-inputs -show-ports -dump_json {_ys_path(compare_json)} -dump_vcd {_ys_path(compare_vcd)}",
        ])
        _write(compare_script, script)
        command = _run([yosys, "-s", str(compare_script)], compare_log, timeout, output_dir.parent)
        text = Path(compare_log).read_text(encoding="utf-8", errors="replace")
        verdict, reason = classify_formal_log(text, command.returncode, timed_out=command.timed_out)
        model = parse_model(text)
        comparison = {
            "status": verdict.value,
            "reason": reason,
            "runtime_seconds": command.runtime_seconds,
            "returncode": command.returncode,
            "script": str(compare_script),
            "log": str(compare_log),
            "miter": str(compare_miter),
            "counterexample_json": str(compare_json) if compare_json.is_file() else None,
            "counterexample_vcd": str(compare_vcd) if compare_vcd.is_file() else None,
            "model": model,
        }
        base["formal_check_count"] += 1
        base["formal_runtime_seconds"] += command.runtime_seconds or 0.0
    else:
        comparison["reason"] = "The normal or instrumented final candidate was unavailable."
        base["errors"].append(comparison["reason"])
    base["flow_comparison"] = comparison

    status, first_stage, previous_stage, interval, errors = _localization_status(records)
    base["status"] = status
    base["first_divergent_stage"] = first_stage
    base["previous_stage"] = previous_stage
    base["divergence_interval"] = interval
    base["errors"].extend(errors)
    _apply_localization_guards(base, result, records, comparison.get("status", Verdict.NOT_EXECUTED.value))
    base["time_to_first_divergence_seconds"] = first_divergence_time
    base["unexecuted_stages"] = [record.name for record in records if record.verdict == Verdict.NOT_EXECUTED]
    base["total_runtime_seconds"] = time.monotonic() - start
    base["miter"] = str(miter)
    return base
