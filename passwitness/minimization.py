"""Public Phase 4 minimization workflow."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from .models import Verdict
from .reduction_oracle import (
    PRESERVE_FUNCTIONAL_FAILURE,
    PRESERVE_LOCALIZED_FAILURE,
    OracleConfig,
    ReductionOracle,
)
from .reducer import minimize_marked_blocks, reducer_identity, source_metrics


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replace_root(value: Any, old: Path, new: Path) -> Any:
    if isinstance(value, dict):
        return {key: _replace_root(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_root(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(str(old), str(new))
    return value


def _rewrite_scratch_files(root: Path, old: Path, new: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".vcd", ".rtlil", ".il"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        rewritten = text.replace(str(old), str(new))
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")


def minimize(
    *,
    rtl: Path,
    top: str,
    flow: Path,
    output_dir: Path,
    yosys: str = "yosys",
    target_stage: str | None = None,
    mode: str = PRESERVE_FUNCTIONAL_FAILURE,
    patched_yosys: str | None = None,
    require_patched_pass: bool = False,
    timeout: float = 120.0,
    max_runtime: float = 1800.0,
    max_evaluations: int = 100,
    max_parallel_evaluations: int = 1,
    temp_dir: Path | None = None,
    parameters: tuple[str, ...] = (),
    backend: str = "yosys-sat",
) -> dict[str, Any]:
    started = time.monotonic()
    rtl = rtl.resolve()
    flow = flow.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if max_parallel_evaluations != 1:
        result = {
            "schema_version": 4,
            "status": Verdict.SETUP_ERROR.value,
            "errors": ["This Phase 4 reducer is deliberately sequential; max_parallel_evaluations must be 1."],
        }
        _write(output_dir / "result.json", result)
        return result
    scratch = output_dir if temp_dir is None else (temp_dir.resolve() / f"passwitness-{output_dir.name}")
    scratch.mkdir(parents=True, exist_ok=True)
    if not rtl.is_file():
        result = {"schema_version": 4, "status": Verdict.SETUP_ERROR.value, "errors": [f"RTL file does not exist: {rtl}"]}
        _write(output_dir / "result.json", result)
        return result
    if not flow.is_file():
        result = {"schema_version": 4, "status": Verdict.SETUP_ERROR.value, "errors": [f"Flow file does not exist: {flow}"]}
        _write(output_dir / "result.json", result)
        return result
    try:
        search_started = time.monotonic()
        config = OracleConfig(
            top=top,
            flow=flow,
            yosys=yosys,
            output_dir=scratch / "oracle",
            mode=mode,
            target_stage=target_stage,
            patched_yosys=patched_yosys,
            require_patched_pass=require_patched_pass,
            timeout=timeout,
            parameters=parameters,
            backend=backend,
        )
        oracle = ReductionOracle(config)
        reduction = minimize_marked_blocks(
            rtl=rtl,
            oracle=oracle,
            work_dir=scratch / "reduction-work",
            max_evaluations=max_evaluations,
            max_runtime=max_runtime,
        )
        search_runtime = time.monotonic() - search_started
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 4, "status": Verdict.SETUP_ERROR.value, "errors": [str(exc)]}
        _write(output_dir / "result.json", result)
        return result

    # Always reverify from an independent oracle root.  This bypasses the
    # search cache and copies the selected candidate into a fresh directory.
    final_config = OracleConfig(
        top=top,
        flow=flow,
        yosys=yosys,
        output_dir=scratch / "final-reverification",
        mode=mode,
        target_stage=target_stage,
        patched_yosys=patched_yosys,
        require_patched_pass=require_patched_pass,
        timeout=timeout,
        parameters=parameters,
        backend=backend,
    )
    final_oracle = ReductionOracle(final_config)
    final = final_oracle.evaluate(reduction.best_source, force=True, label="final-reverification")
    if scratch != output_dir:
        for name in ("oracle", "reduction-work", "final-reverification"):
            shutil.copytree(scratch / name, output_dir / name, dirs_exist_ok=True)
        _rewrite_scratch_files(output_dir, scratch, output_dir)
    original_metrics = source_metrics(rtl)
    reduced_metrics = source_metrics(reduction.best_source)
    reduction_percent = {
        key: round((1.0 - reduced_metrics[key] / original_metrics[key]) * 100.0, 2) if original_metrics[key] else 0.0
        for key in ("bytes", "lines")
    }
    accepted_reduction = reduced_metrics["bytes"] < original_metrics["bytes"] or reduced_metrics["lines"] < original_metrics["lines"]
    final_verified = final.accepted
    if accepted_reduction and final_verified:
        status = "BUDGET_EXHAUSTED_WITH_REDUCTION" if reduction.budget_exhausted else "VERIFIED_REDUCTION"
    elif not accepted_reduction and final_verified:
        status = "NO_REDUCTION_FOUND"
    else:
        status = "UNVERIFIED_REDUCTION"
    verification_status = "VERIFIED_REDUCTION" if accepted_reduction and final_verified else (
        "VERIFIED_FAILURE_NO_REDUCTION" if final_verified else "UNVERIFIED"
    )

    history = [item.to_dict() for item in reduction.history]
    result: dict[str, Any] = {
        "schema_version": 4,
        "status": status,
        "verification_status": verification_status,
        "input_design": str(rtl),
        "minimized_design": str(reduction.best_source.resolve()),
        "top_module": top,
        "flow": str(flow),
        "parameters": list(parameters),
        "oracle_mode": mode,
        "target_stage": target_stage,
        "configuration": {
            "yosys": yosys,
            "patched_yosys": patched_yosys,
            "require_patched_pass": require_patched_pass,
            "backend": backend,
            "candidate_timeout_seconds": timeout,
            "max_runtime_seconds": max_runtime,
            "max_evaluations": max_evaluations,
            "max_parallel_evaluations": max_parallel_evaluations,
            "temporary_directory": str(scratch),
            "golden_reference": "each candidate is independently elaborated from that candidate source",
        },
        "reducer": reducer_identity(),
        "metrics": {
            "original": original_metrics,
            "reduced": reduced_metrics,
            "reduction_percent": reduction_percent,
        },
        "audit": {
            **reduction.stats,
            "candidate_evaluations": oracle.count,
            "unique_candidate_hashes": reduction.stats.get("unique_candidate_hashes", 0),
            "oracle_executions": oracle.oracle_executions,
            "cache_hits": oracle.cache_hits,
            "accepted_candidates": reduction.stats.get("valid_oracle_accepted_candidates", 0),
            "accepted_reductions": reduction.stats.get("strict_size_improvements", 0),
            "unique_accepted_candidates": reduction.stats.get("unique_valid_oracle_accepted_candidates", 0),
            "rejected_candidates": reduction.stats.get("rejected_candidates", 0),
            "formal_checks": oracle.formal_checks + final_oracle.formal_checks,
            "search_formal_checks": oracle.formal_checks,
            "reduction_runtime_seconds": search_runtime,
            "final_reverification_runtime_seconds": final.runtime_seconds,
            "final_independent_reverification": {
                "executed": True,
                "accepted": final.accepted,
                "oracle_executions": final_oracle.oracle_executions,
                "cache_hits": final_oracle.cache_hits,
            },
            "budget_exhausted": reduction.budget_exhausted,
            "history": history,
        },
        "baseline": history[0]["oracle"] if history else None,
        "final_reverification": final.to_dict(),
        "reason": reduction.reason,
        "errors": [] if final_verified else [f"Independent final verification rejected the candidate: {final.reason}"],
        "portable_package": None,
    }
    if scratch != output_dir:
        result = _replace_root(result, scratch, output_dir)
        result["configuration"]["temporary_directory"] = str(scratch)
    _write(output_dir / "result.json", result)
    _write(output_dir / "reduction-history.json", history)
    from .reports import write_minimization_report

    write_minimization_report(result, output_dir / "report.md")
    from .reduction_package import build_reduction_package

    package_reduced = output_dir / "reduction-work" / reduction.best_source.name if scratch != output_dir else reduction.best_source
    package = build_reduction_package(result, output_dir=output_dir, original=rtl, reduced=package_reduced, flow=flow)
    result["portable_package"] = str(package)
    _write(output_dir / "result.json", result)
    write_minimization_report(result, output_dir / "report.md")
    # Keep the portable copy synchronized after adding its final package path.
    build_reduction_package(result, output_dir=output_dir, original=rtl, reduced=package_reduced, flow=flow)
    return result
