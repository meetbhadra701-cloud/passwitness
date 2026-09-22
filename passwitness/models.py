from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED = "UNSUPPORTED"
    SETUP_ERROR = "SETUP_ERROR"
    NOT_EXECUTED = "NOT_EXECUTED"


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int | None
    runtime_seconds: float | None
    log_path: str
    timed_out: bool = False


@dataclass
class ReplayResult:
    status: str
    reason: str
    runtime_seconds: float | None = None
    log_path: str | None = None
    input_values: dict[str, Any] = field(default_factory=dict)
    reference_outputs: dict[str, Any] = field(default_factory=dict)
    candidate_outputs: dict[str, Any] = field(default_factory=dict)
    mismatch: Any = None
    backend: str = "yosys-sat"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "runtime_seconds": self.runtime_seconds,
            "log_path": self.log_path,
            "input_values": self.input_values,
            "reference_outputs": self.reference_outputs,
            "candidate_outputs": self.candidate_outputs,
            "mismatch": self.mismatch,
            "backend": self.backend,
            "kind": "fixed_witness_replay",
            "is_formal_proof": False,
        }


@dataclass
class Port:
    name: str
    direction: str
    width: int
    signed: bool = False


@dataclass
class FormalResult:
    verdict: Verdict = Verdict.NOT_EXECUTED
    reason: str = "Formal check was not executed."
    runtime_seconds: float | None = None
    log_path: str | None = None
    counterexample_json: str | None = None
    counterexample_vcd: str | None = None
    model: dict[str, dict[str, Any]] = field(default_factory=dict)
    backend: str = "yosys-sat"


@dataclass
class CheckpointRecord:
    name: str
    index: int
    transition: str
    snapshot_path: str | None = None
    produced: bool = False
    verdict: Verdict = Verdict.NOT_EXECUTED
    reason: str = "Checkpoint proof was not executed."
    proof_runtime_seconds: float | None = None
    proof_log_path: str | None = None
    proof_script_path: str | None = None
    counterexample_json: str | None = None
    counterexample_vcd: str | None = None
    model: dict[str, dict[str, Any]] = field(default_factory=dict)
    witness_replay: dict[str, Any] | None = None
    preparation_commands: list[str] = field(default_factory=list)
    capture_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "index": self.index,
            "transition": self.transition,
            "snapshot_path": self.snapshot_path,
            "produced": self.produced,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "proof_runtime_seconds": self.proof_runtime_seconds,
            "proof_log_path": self.proof_log_path,
            "proof_script_path": self.proof_script_path,
            "counterexample_json": self.counterexample_json,
            "counterexample_vcd": self.counterexample_vcd,
            "model": self.model,
            "witness_replay": self.witness_replay,
            "preparation_commands": self.preparation_commands,
            "capture_commands": self.capture_commands,
        }
        return payload


@dataclass
class AnalysisResult:
    status: Verdict
    rtl: str
    top: str
    flow: str
    output_dir: str
    parameters: dict[str, str]
    tool: dict[str, Any] = field(default_factory=dict)
    synthesis: dict[str, Any] = field(default_factory=dict)
    formal: FormalResult = field(default_factory=FormalResult)
    paths: dict[str, str] = field(default_factory=dict)
    counterexample: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    inferences: list[str] = field(default_factory=list)
    unexecuted_checks: list[str] = field(default_factory=list)
    localization: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        formal = {
            "verdict": self.formal.verdict.value,
            "reason": self.formal.reason,
            "runtime_seconds": self.formal.runtime_seconds,
            "log_path": self.formal.log_path,
            "counterexample_json": self.formal.counterexample_json,
            "counterexample_vcd": self.formal.counterexample_vcd,
            "model": self.formal.model,
            "backend": self.formal.backend,
        }
        payload = {
            "schema_version": 3 if self.localization is not None and "flow_fidelity" in self.localization else (2 if self.localization is not None else 1),
            "status": self.status.value,
            "input_design": self.rtl,
            "top_module": self.top,
            "parameters": self.parameters,
            "flow": self.flow,
            "output_directory": self.output_dir,
            "tool": self.tool,
            "synthesis": self.synthesis,
            "formal": formal,
            "paths": self.paths,
            "counterexample": self.counterexample,
            "errors": self.errors,
            "verified_facts": self.verified_facts,
            "inferences": self.inferences,
            "unexecuted_checks": self.unexecuted_checks,
        }
        if self.localization is not None:
            payload["localization"] = self.localization
        return payload
