"""Automatic localization over real, serialized synthesis checkpoints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .backends import BackendProof, FormalBackend
from .checkpoints import build_instrumented_flow
from .formal import write_miter
from .models import AnalysisResult, CheckpointRecord, Port, ReplayResult, Verdict
from .runner import _run, _ys_path


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
    backend: FormalBackend,
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
) -> BackendProof:
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
    return backend.execute(script_path, log_path)


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
    if comparison_status == Verdict.FAIL.value:
        base["status"] = "INSTRUMENTATION_MISMATCH"
        base["errors"].append(
            "The instrumented final candidate is functionally different from the original Phase 1 candidate."
        )
    elif comparison_status != Verdict.PASS.value:
        base["status"] = "INCONCLUSIVE"
        base["errors"].append("Flow fidelity was not established by a completed final-candidate comparison.")
    final_checkpoint = records[-1].verdict.value if records else Verdict.NOT_EXECUTED.value
    if result.formal.verdict.value != final_checkpoint:
        base["status"] = "INCONCLUSIVE"
        base["errors"].append("The instrumented final checkpoint verdict differs from the Phase 1 final verdict.")
    return base


def _replay_script(
    *,
    rtl: Path,
    candidate: Path,
    candidate_kind: str,
    candidate_module: str,
    miter: Path,
    input_values: dict[str, str],
    ports: list[Port],
) -> str:
    lines: list[str] = []
    if candidate_kind == "rtlil":
        lines.extend([
            f"read_rtlil {_ys_path(candidate)}",
            f"rename {candidate_module} passwitness_candidate",
            "hierarchy -top passwitness_candidate",
        ])
    else:
        lines.append(f"read_verilog {_ys_path(candidate)}")
    lines.extend([
        f"read_verilog -sv {_ys_path(rtl)}",
        f"read_verilog {_ys_path(miter)}",
        "hierarchy -top passwitness_miter",
        "prep -top passwitness_miter",
        "flatten",
        "opt",
        "sat -set-def-inputs " + " ".join(f"-set {name} {value}" for name, value in input_values.items()) + " " + " ".join(
            f"-show {name}" for name in [
                *(port.name for port in ports if port.direction == "input"),
                *(f"reference_{port.name}" for port in ports if port.direction == "output"),
                *(f"candidate_{port.name}" for port in ports if port.direction == "output"),
                "mismatch",
            ]
        ),
    ])
    return "\n".join(lines) + "\n"


def _replay_one(
    *,
    backend: FormalBackend,
    rtl: Path,
    candidate: Path,
    candidate_kind: str,
    candidate_module: str,
    miter: Path,
    ports: list[Port],
    witness_model: dict[str, dict[str, str | int]],
    expected_mismatch: int,
    script_path: Path,
    log_path: Path,
    target: str,
) -> ReplayResult:
    inputs: dict[str, str] = {}
    for port in ports:
        if port.direction != "input" or port.name not in witness_model:
            continue
        value = witness_model[port.name]
        binary = str(value.get("binary", ""))
        if any(bit.lower() not in "01" for bit in binary):
            return ReplayResult("UNCONFIRMED", f"Witness input {port.name} contains an undefined bit.", input_values={}, backend=backend.name)
        inputs[port.name] = f"{port.width}'b{binary}"
    if len(inputs) != sum(port.direction == "input" for port in ports):
        return ReplayResult("UNCONFIRMED", "The formal witness did not contain every input value.", input_values=inputs, backend=backend.name)
    _write(script_path, _replay_script(
        rtl=rtl,
        candidate=candidate,
        candidate_kind=candidate_kind,
        candidate_module=candidate_module,
        miter=miter,
        input_values=inputs,
        ports=ports,
    ))
    execution = backend.execute(script_path, log_path, mode="replay")
    if execution.verdict != Verdict.PASS:
        status = execution.verdict.value
        return ReplayResult(status, execution.reason, execution.runtime_seconds, execution.log_path, inputs, backend=backend.name)
    model = execution.model
    mismatch = model.get("mismatch")
    if mismatch is None:
        return ReplayResult("UNCONFIRMED", "Replay returned no mismatch signal.", execution.runtime_seconds, execution.log_path, inputs, backend=backend.name)
    actual = int(mismatch.get("decimal", 0))
    reference = {
        port.name: model[f"reference_{port.name}"]
        for port in ports if port.direction == "output" and f"reference_{port.name}" in model
    }
    candidate_outputs = {
        port.name: model[f"candidate_{port.name}"]
        for port in ports if port.direction == "output" and f"candidate_{port.name}" in model
    }
    status = "CONFIRMED" if actual == expected_mismatch else "MISMATCH"
    return ReplayResult(
        status=status,
        reason=f"Replay target {target} produced mismatch={actual}; expected {expected_mismatch}.",
        runtime_seconds=execution.runtime_seconds,
        log_path=execution.log_path,
        input_values=inputs,
        reference_outputs=reference,
        candidate_outputs=candidate_outputs,
        mismatch=mismatch,
        backend=backend.name,
    )


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
    backend: FormalBackend,
) -> dict[str, Any]:
    start = time.monotonic()
    work = output_dir / "localization"
    logs = work / "logs"
    proofs = work / "proofs"
    witnesses = work / "witnesses"
    for path in (work, logs, proofs, witnesses):
        path.mkdir(parents=True, exist_ok=True)
    plan = build_instrumented_flow(
        flow,
        top,
        work,
        rtl,
        parameters,
        tool_version=str(result.tool.get("yosys_reported_version", result.tool.get("version", ""))),
    )
    flow_fidelity: dict[str, Any] = {
        "status": "NOT_EXECUTED",
        "original_commands": plan.original_commands or [],
        "instrumented_commands": plan.instrumented_commands or [],
        "added_commands": plan.added_commands or [],
        "expanded_commands": plan.expanded_commands or [],
        "execution_order": plan.execution_order or [],
        "selected_options": plan.selected_options or {},
        "catalog_id": plan.catalog_id,
        "tool_version": plan.tool_version,
        "original_final_representation": str(normal_candidate),
        "instrumented_final_representation": str(plan.final_snapshot) if plan.final_snapshot else None,
        "comparison": None,
        "reason": plan.reason,
    }
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
        "flow_fidelity": flow_fidelity,
        "backend": backend.name,
        "backend_capabilities": backend.capabilities,
        "witness_replay": {"status": "NOT_EXECUTED", "targets": {}},
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
        flow_fidelity["status"] = "UNSUPPORTED"
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
        "original_commands": plan.original_commands or [],
        "instrumented_commands": plan.instrumented_commands or [],
        "added_commands": plan.added_commands or [],
        "expanded_commands": plan.expanded_commands or [],
        "execution_order": plan.execution_order or [],
    }
    base["synthesis_runtime_seconds"] = synthesis.runtime_seconds or 0.0
    if synthesis.timed_out:
        flow_fidelity["status"] = Verdict.TIMEOUT.value
        base["status"] = "INCONCLUSIVE"
        base["errors"].append("Instrumented synthesis timed out before all checkpoints were captured.")
        base["total_runtime_seconds"] = time.monotonic() - start
        return base
    if synthesis.returncode != 0:
        flow_fidelity["status"] = Verdict.SETUP_ERROR.value
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
            proof = _run_proof(
                backend=backend,
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
            record.verdict = proof.verdict
            record.reason = proof.reason
            record.proof_runtime_seconds = proof.runtime_seconds
            record.model = proof.model
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
        comparison_proof = backend.execute(compare_script, compare_log)
        comparison = {
            "status": comparison_proof.verdict.value,
            "reason": comparison_proof.reason,
            "runtime_seconds": comparison_proof.runtime_seconds,
            "returncode": comparison_proof.returncode,
            "script": str(compare_script),
            "log": str(compare_log),
            "miter": str(compare_miter),
            "counterexample_json": str(compare_json) if compare_json.is_file() else None,
            "counterexample_vcd": str(compare_vcd) if compare_vcd.is_file() else None,
            "model": comparison_proof.model,
            "backend": backend.name,
        }
        base["formal_check_count"] += 1
        base["formal_runtime_seconds"] += comparison_proof.runtime_seconds or 0.0
    else:
        comparison["reason"] = "The normal or instrumented final candidate was unavailable."
        base["errors"].append(comparison["reason"])
    base["flow_comparison"] = comparison
    flow_fidelity["status"] = comparison.get("status", Verdict.NOT_EXECUTED.value)
    flow_fidelity["comparison"] = comparison

    status, first_stage, previous_stage, interval, errors = _localization_status(records)
    base["status"] = status
    base["first_divergent_stage"] = first_stage
    base["previous_stage"] = previous_stage
    base["divergence_interval"] = interval
    base["errors"].extend(errors)
    _apply_localization_guards(base, result, records, comparison.get("status", Verdict.NOT_EXECUTED.value))
    if base["status"] == "LOCALIZED":
        failing_index = next((index for index, record in enumerate(records) if record.verdict == Verdict.FAIL), None)
        if failing_index is not None and failing_index > 0:
            failing = records[failing_index]
            previous = records[failing_index - 1]
            replay_dir = work / "replay"
            replay_dir.mkdir(parents=True, exist_ok=True)
            targets = {
                "previous_checkpoint": (previous.snapshot_path, "rtlil", top, 0),
                "failing_checkpoint": (failing.snapshot_path, "rtlil", top, 1),
                "original_final": (str(normal_candidate), "verilog", "passwitness_candidate", 1 if result.formal.verdict == Verdict.FAIL else 0),
            }
            replay_targets: dict[str, dict[str, Any]] = {}
            for target, (candidate_path, candidate_kind, candidate_module, expected) in targets.items():
                if not candidate_path or not Path(candidate_path).is_file():
                    replay_targets[target] = ReplayResult("SETUP_ERROR", "Replay candidate representation is unavailable.", backend=backend.name).to_dict()
                    continue
                replay = _replay_one(
                    backend=backend,
                    rtl=rtl,
                    candidate=Path(candidate_path),
                    candidate_kind=candidate_kind,
                    candidate_module=candidate_module,
                    miter=miter,
                    ports=ports,
                    witness_model=failing.model,
                    expected_mismatch=expected,
                    script_path=replay_dir / f"{target}.ys",
                    log_path=replay_dir / f"{target}.log",
                    target=target,
                )
                replay_targets[target] = replay.to_dict()
            base["witness_replay"] = {
                "status": "CONFIRMED" if all(item.get("status") == "CONFIRMED" for item in replay_targets.values()) else "UNCONFIRMED",
                "witness_source": failing.name,
                "targets": replay_targets,
            }
            previous.witness_replay = replay_targets.get("previous_checkpoint")
            failing.witness_replay = replay_targets.get("failing_checkpoint")
    base["time_to_first_divergence_seconds"] = first_divergence_time
    base["checkpoints"] = [_record_dict(record) for record in records]
    base["unexecuted_stages"] = [record.name for record in records if record.verdict == Verdict.NOT_EXECUTED]
    base["total_runtime_seconds"] = time.monotonic() - start
    base["miter"] = str(miter)
    return base
