"""Narrow formal-backend interface used by analysis and localization."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .formal import parse_model
from .models import Verdict
from .verdict import classify_formal_log


@dataclass
class BackendProof:
    verdict: Verdict
    reason: str
    runtime_seconds: float
    log_path: str
    model: dict[str, dict[str, str | int]] = field(default_factory=dict)
    returncode: int | None = None
    timed_out: bool = False


class FormalBackend(Protocol):
    name: str
    capabilities: dict[str, Any]

    def execute(self, script_path: Path, log_path: Path, *, mode: str = "proof") -> BackendProof:
        ...


class YosysSatBackend:
    """Execute documented Yosys SAT scripts and use the shared verdict parser."""

    name = "yosys-sat"
    capabilities = {
        "design_class": "small combinational bit-vector circuits",
        "proof_property": "explicit output mismatch == 0",
        "witness": "Yosys SAT model plus JSON/VCD dumps",
    }

    def __init__(self, yosys: str, cwd: Path, timeout: float | None):
        self.yosys = yosys
        self.cwd = cwd
        self.timeout = timeout

    def execute(self, script_path: Path, log_path: Path, *, mode: str = "proof") -> BackendProof:
        # Import lazily to keep process execution independent from the backend
        # interface while preserving the Phase 1 runner's error handling.
        from .runner import _run

        command = _run([self.yosys, "-s", str(script_path)], log_path, self.timeout, self.cwd)
        text = Path(command.log_path).read_text(encoding="utf-8", errors="replace")
        if mode == "replay":
            if command.timed_out:
                verdict, reason = Verdict.TIMEOUT, "The fixed-witness replay exceeded its configured timeout."
            elif command.returncode != 0 or "ERROR:" in text or "FATAL:" in text:
                verdict, reason = Verdict.SETUP_ERROR, "The fixed-witness replay did not execute successfully."
            elif "SAT solving finished - model found:" in text:
                verdict, reason = Verdict.PASS, "The fixed-witness replay executed and returned a model."
            else:
                verdict, reason = Verdict.SETUP_ERROR, "The fixed-witness replay produced no recognizable model."
        else:
            verdict, reason = classify_formal_log(text, command.returncode, timed_out=command.timed_out)
        return BackendProof(
            verdict=verdict,
            reason=reason,
            runtime_seconds=command.runtime_seconds or 0.0,
            log_path=command.log_path,
            model=parse_model(text),
            returncode=command.returncode,
            timed_out=command.timed_out,
        )


class EqyBackend:
    """Capability placeholder for a future EQY adapter; never claims execution."""

    name = "eqy"
    capabilities = {
        "design_class": "future adapter",
        "status": "adapter not implemented in Phase 3",
    }

    @staticmethod
    def available(executable: str = "eqy") -> bool:
        return shutil.which(executable) is not None

    def execute(self, script_path: Path, log_path: Path, *, mode: str = "proof") -> BackendProof:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("EQY backend is not implemented in Phase 3.\n", encoding="utf-8")
        return BackendProof(
            verdict=Verdict.UNSUPPORTED,
            reason="EQY backend is documented but not implemented in Phase 3.",
            runtime_seconds=0.0,
            log_path=str(log_path),
        )


def make_backend(name: str, yosys: str, cwd: Path, timeout: float | None) -> FormalBackend:
    if name == "yosys-sat":
        return YosysSatBackend(yosys, cwd, timeout)
    if name == "eqy":
        return EqyBackend()
    raise ValueError(f"Unsupported formal backend: {name!r}")
