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

    def to_dict(self) -> dict[str, Any]:
        formal = {
            "verdict": self.formal.verdict.value,
            "reason": self.formal.reason,
            "runtime_seconds": self.formal.runtime_seconds,
            "log_path": self.formal.log_path,
            "counterexample_json": self.formal.counterexample_json,
            "counterexample_vcd": self.formal.counterexample_vcd,
            "model": self.formal.model,
        }
        return {
            "schema_version": 1,
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
