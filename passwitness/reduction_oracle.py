"""Formal-guided interestingness oracle for source reduction.

The oracle deliberately treats the candidate source as its own golden RTL.
This is the central safety property of reduction: a smaller candidate must
still demonstrate a synthesis failure against the behavior it describes, not
against the original unreduced design.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Verdict
from .runner import _sha256_file, analyze


PRESERVE_FUNCTIONAL_FAILURE = "PRESERVE_FUNCTIONAL_FAILURE"
PRESERVE_LOCALIZED_FAILURE = "PRESERVE_LOCALIZED_FAILURE"


def _tool_hash(tool: str) -> str | None:
    path = Path(tool)
    if not path.is_file():
        found = shutil.which(tool)
        path = Path(found) if found else path
    return _sha256_file(path) if path.is_file() else None


@dataclass(frozen=True)
class OracleConfig:
    top: str
    flow: Path
    yosys: str
    output_dir: Path
    mode: str = PRESERVE_FUNCTIONAL_FAILURE
    target_stage: str | None = None
    patched_yosys: str | None = None
    require_patched_pass: bool = False
    timeout: float = 120.0
    parameters: tuple[str, ...] = ()
    backend: str = "yosys-sat"


@dataclass
class OracleResult:
    accepted: bool
    candidate_hash: str
    candidate_path: str
    output_dir: str
    reason: str
    mode: str
    overall_verdict: str = Verdict.NOT_EXECUTED.value
    localization_status: str = "NOT_EXECUTED"
    flow_fidelity_status: str = "NOT_EXECUTED"
    witness_replay_status: str = "NOT_EXECUTED"
    first_divergent_stage: str | None = None
    previous_stage: str | None = None
    patched_verdict: str | None = None
    formal_checks: int = 0
    runtime_seconds: float = 0.0
    cached: bool = False
    analysis_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "candidate_hash": self.candidate_hash,
            "candidate_path": self.candidate_path,
            "output_dir": self.output_dir,
            "reason": self.reason,
            "mode": self.mode,
            "overall_verdict": self.overall_verdict,
            "localization_status": self.localization_status,
            "flow_fidelity_status": self.flow_fidelity_status,
            "witness_replay_status": self.witness_replay_status,
            "first_divergent_stage": self.first_divergent_stage,
            "previous_stage": self.previous_stage,
            "patched_verdict": self.patched_verdict,
            "formal_checks": self.formal_checks,
            "runtime_seconds": self.runtime_seconds,
            "cached": self.cached,
            "analysis_result": self.analysis_result,
        }


class ReductionOracle:
    """Evaluate candidates using the same trusted Phase 3 proof path."""

    def __init__(self, config: OracleConfig):
        if config.mode not in (PRESERVE_FUNCTIONAL_FAILURE, PRESERVE_LOCALIZED_FAILURE):
            raise ValueError(f"Unsupported reduction oracle mode: {config.mode}")
        if config.mode == PRESERVE_LOCALIZED_FAILURE and not config.target_stage:
            raise ValueError("PRESERVE_LOCALIZED_FAILURE requires --target-stage")
        self.config = config
        self.root = config.output_dir.resolve()
        self.cache = self.root / "oracle-cache"
        self.evaluations = self.root / "evaluations"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.evaluations.mkdir(parents=True, exist_ok=True)
        self.count = 0
        self.formal_checks = 0
        self.accepted = 0
        self.rejected = 0
        self.oracle_executions = 0
        self.cache_hits = 0
        self.unique_candidate_hashes: set[str] = set()

    def _configuration_key(self, candidate_hash: str) -> str:
        flow_hash = _sha256_file(self.config.flow.resolve())
        material = {
            "candidate_hash": candidate_hash,
            "flow_hash": flow_hash,
            "top": self.config.top,
            "mode": self.config.mode,
            "target_stage": self.config.target_stage,
            "yosys": str(Path(self.config.yosys).resolve()) if Path(self.config.yosys).exists() else self.config.yosys,
            "yosys_sha256": _tool_hash(self.config.yosys),
            "patched_yosys": self.config.patched_yosys,
            "patched_sha256": _tool_hash(self.config.patched_yosys) if self.config.patched_yosys else None,
            "require_patched_pass": self.config.require_patched_pass,
            "timeout": self.config.timeout,
            "parameters": self.config.parameters,
            "backend": self.config.backend,
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _replay_status(analysis: dict[str, Any]) -> str:
        return str((analysis.get("localization") or {}).get("witness_replay", {}).get("status", "NOT_EXECUTED"))

    @staticmethod
    def _flow_status(analysis: dict[str, Any]) -> str:
        return str((analysis.get("localization") or {}).get("flow_fidelity", {}).get("status", "NOT_EXECUTED"))

    @staticmethod
    def _formal_count(analysis: dict[str, Any]) -> int:
        return int((analysis.get("localization") or {}).get("formal_check_count", 0)) + 1

    def _evaluate_analysis(self, analysis: dict[str, Any], candidate_hash: str, candidate_path: Path, output: Path) -> OracleResult:
        localization = analysis.get("localization") or {}
        overall = str(analysis.get("status", Verdict.NOT_EXECUTED.value))
        formal = analysis.get("formal") or {}
        replay = self._replay_status(analysis)
        fidelity = self._flow_status(analysis)
        first = localization.get("first_divergent_stage")
        previous = localization.get("previous_stage")
        reasons: list[str] = []

        if overall != Verdict.FAIL.value or formal.get("verdict") != Verdict.FAIL.value:
            reasons.append(f"candidate final proof is {overall}, not FAIL")
        if not formal.get("counterexample_json") or not Path(formal["counterexample_json"]).is_file():
            reasons.append("no preserved formal counterexample is available")
        if fidelity != Verdict.PASS.value:
            reasons.append(f"flow fidelity is {fidelity}, not PASS")
        if replay != "CONFIRMED":
            reasons.append(f"fixed-witness replay is {replay}, not CONFIRMED")

        if self.config.mode == PRESERVE_LOCALIZED_FAILURE:
            if localization.get("status") != "LOCALIZED":
                reasons.append(f"localization status is {localization.get('status')}, not LOCALIZED")
            if first != self.config.target_stage:
                reasons.append(f"first divergent stage is {first!r}, expected {self.config.target_stage!r}")
            records = localization.get("checkpoints", [])
            target = next((record for record in records if record.get("transition") == self.config.target_stage), None)
            if target is None or target.get("verdict") != Verdict.FAIL.value:
                reasons.append("the selected target checkpoint is not a verified FAIL")
            prior = next((record for record in records if record.get("name") == previous), None)
            if prior is None or prior.get("verdict") != Verdict.PASS.value:
                reasons.append("the selected previous checkpoint is not a verified PASS")

        return OracleResult(
            accepted=not reasons,
            candidate_hash=candidate_hash,
            candidate_path=str(candidate_path),
            output_dir=str(output),
            reason="accepted: formal failure, fidelity, localization contract, and replay confirmed" if not reasons else "; ".join(reasons),
            mode=self.config.mode,
            overall_verdict=overall,
            localization_status=str(localization.get("status", "NOT_EXECUTED")),
            flow_fidelity_status=fidelity,
            witness_replay_status=replay,
            first_divergent_stage=first,
            previous_stage=previous,
            formal_checks=self._formal_count(analysis),
            runtime_seconds=float((localization or {}).get("total_runtime_seconds") or formal.get("runtime_seconds") or 0.0),
            analysis_result=analysis,
        )

    def evaluate(self, candidate: Path, *, force: bool = False, label: str | None = None) -> OracleResult:
        source = candidate.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Candidate RTL does not exist: {source}")
        contents = source.read_bytes()
        candidate_hash = hashlib.sha256(contents).hexdigest()
        self.unique_candidate_hashes.add(candidate_hash)
        key = self._configuration_key(candidate_hash)
        cache_path = self.cache / f"{key}.json"
        if cache_path.is_file() and not force:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["cached"] = True
            result = OracleResult(**cached)
            self.cache_hits += 1
            self.count += 1
            self.accepted += int(result.accepted)
            self.rejected += int(not result.accepted)
            return result

        self.count += 1
        self.oracle_executions += 1
        started = time.monotonic()
        output = self.evaluations / key
        input_dir = output / "candidate"
        input_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = input_dir / "source.v"
        candidate_path.write_bytes(contents)
        analysis_dir = output / "analysis"
        analysis = analyze(
            rtl=candidate_path,
            top=self.config.top,
            flow=self.config.flow,
            output_dir=analysis_dir,
            yosys=self.config.yosys,
            parameters=list(self.config.parameters),
            timeout=self.config.timeout,
            localize=True,
            backend_name=self.config.backend,
        )
        result = self._evaluate_analysis(analysis.to_dict(), candidate_hash, candidate_path, output)
        self.formal_checks += result.formal_checks

        if result.accepted and self.config.patched_yosys:
            control_dir = output / "patched-control"
            control = analyze(
                rtl=candidate_path,
                top=self.config.top,
                flow=self.config.flow,
                output_dir=control_dir,
                yosys=self.config.patched_yosys,
                parameters=list(self.config.parameters),
                timeout=self.config.timeout,
                localize=False,
                backend_name=self.config.backend,
            )
            result.patched_verdict = control.status.value
            result.formal_checks += 1
            if self.config.require_patched_pass and control.status is not Verdict.PASS:
                result.accepted = False
                result.reason += f"; patched control is {control.status.value}, not PASS"
            result.analysis_result["patched_control"] = control.to_dict()
        result.runtime_seconds = time.monotonic() - started
        result.cached = False
        self.accepted += int(result.accepted)
        self.rejected += int(not result.accepted)
        cache_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
