"""Bounded source reduction driven by :mod:`reduction_oracle`.

This is intentionally not a Verilog reducer.  It removes only complete blocks
delimited by explicit PassWitness markers.  That makes the transformation
auditable and preserves the user's choice of parser/reducer for future
integrations such as C-Reduce.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .reduction_oracle import OracleResult, ReductionOracle


_BEGIN = re.compile(r"^\s*//\s*passwitness-reduce-begin:\s*([A-Za-z0-9_.-]+)\s*$")
_END = re.compile(r"^\s*//\s*passwitness-reduce-end:\s*([A-Za-z0-9_.-]+)\s*$")


def reducer_identity() -> dict[str, Any]:
    creduce = shutil.which("creduce")
    return {
        "name": "passwitness-marked-block-reducer",
        "version": "0.1",
        "external_reducer": "creduce",
        "external_available": bool(creduce),
        "external_version": _external_version(creduce) if creduce else None,
        "scope": "explicitly marked complete source blocks only",
    }


def _external_version(executable: str | None) -> str | None:
    if not executable:
        return None
    try:
        completed = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (completed.stdout or completed.stderr).strip().splitlines()[0] if (completed.stdout or completed.stderr).strip() else None


@dataclass(frozen=True)
class ReductionBlock:
    name: str
    start_line: int
    end_line: int


def find_blocks(text: str) -> list[ReductionBlock]:
    """Find non-nested, paired reduction markers and reject malformed input."""
    blocks: list[ReductionBlock] = []
    active: tuple[str, int] | None = None
    for index, line in enumerate(text.splitlines(keepends=True)):
        begin = _BEGIN.match(line)
        end = _END.match(line)
        if begin:
            if active is not None:
                raise ValueError("Nested passwitness reduction markers are unsupported")
            active = (begin.group(1), index)
        elif end:
            if active is None:
                raise ValueError(f"Unmatched reduction end marker at line {index + 1}")
            if active[0] != end.group(1):
                raise ValueError(f"Reduction marker name mismatch: {active[0]} versus {end.group(1)}")
            blocks.append(ReductionBlock(active[0], active[1], index))
            active = None
    if active is not None:
        raise ValueError(f"Unmatched reduction begin marker: {active[0]}")
    return blocks


def remove_block(text: str, block: ReductionBlock) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[:block.start_line] + lines[block.end_line + 1 :])


@dataclass
class ReductionHistory:
    candidate_id: str
    candidate_hash: str
    source_bytes: int
    source_lines: int
    accepted: bool
    reason: str
    oracle: dict[str, Any]
    runtime_seconds: float
    block: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_hash": self.candidate_hash,
            "source_bytes": self.source_bytes,
            "source_lines": self.source_lines,
            "accepted": self.accepted,
            "reason": self.reason,
            "oracle": self.oracle,
            "runtime_seconds": self.runtime_seconds,
            "block": self.block,
        }


@dataclass
class ReductionRun:
    status: str
    original: Path
    best_source: Path
    history: list[ReductionHistory] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)
    budget_exhausted: bool = False
    reason: str = ""

    @property
    def runtime_seconds(self) -> float:
        return time.monotonic() - self.started


def minimize_marked_blocks(
    *,
    rtl: Path,
    oracle: ReductionOracle,
    work_dir: Path,
    max_evaluations: int,
    max_runtime: float,
) -> ReductionRun:
    """Try each explicitly marked block, retaining only accepted candidates."""
    rtl = rtl.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    original_text = rtl.read_text(encoding="utf-8")
    blocks = find_blocks(original_text)
    run_started = time.monotonic()
    current_text = original_text
    current_path = work_dir / "best-000-source.v"
    current_path.write_text(current_text, encoding="utf-8")
    baseline = oracle.evaluate(current_path, force=True, label="baseline")
    history = [ReductionHistory(
        candidate_id="baseline",
        candidate_hash=baseline.candidate_hash,
        source_bytes=len(current_text.encode()),
        source_lines=len(current_text.splitlines()),
        accepted=baseline.accepted,
        reason=baseline.reason,
        oracle=baseline.to_dict(),
        runtime_seconds=baseline.runtime_seconds,
    )]
    if not baseline.accepted:
        return ReductionRun("SETUP_ERROR", rtl, current_path, history, reason=f"Original design is not interesting: {baseline.reason}")
    if not blocks:
        return ReductionRun("NO_REDUCTION_FOUND", rtl, current_path, history, reason="No explicitly marked reduction blocks were present.")

    accepted_any = False
    candidate_number = 0
    for block in blocks:
        if len(history) >= max_evaluations or time.monotonic() - run_started > max_runtime:
            return ReductionRun(
                "BUDGET_EXHAUSTED_WITH_REDUCTION" if accepted_any else "NO_REDUCTION_FOUND",
                rtl,
                current_path,
                history,
                budget_exhausted=True,
                reason="Reduction budget exhausted.",
            )
        candidate_text = remove_block(current_text, block)
        candidate_number += 1
        candidate_path = work_dir / f"candidate-{candidate_number:03d}-{block.name}.v"
        candidate_path.write_text(candidate_text, encoding="utf-8")
        started = time.monotonic()
        candidate = oracle.evaluate(candidate_path, label=block.name)
        entry = ReductionHistory(
            candidate_id=f"candidate-{candidate_number:03d}",
            candidate_hash=candidate.candidate_hash,
            source_bytes=len(candidate_text.encode()),
            source_lines=len(candidate_text.splitlines()),
            accepted=candidate.accepted,
            reason=candidate.reason,
            oracle=candidate.to_dict(),
            runtime_seconds=time.monotonic() - started,
            block=block.name,
        )
        history.append(entry)
        if candidate.accepted:
            accepted_any = True
            current_text = candidate_text
            current_path = candidate_path

    status = "REDUCTION_FOUND" if accepted_any else "NO_REDUCTION_FOUND"
    return ReductionRun(status, rtl, current_path, history, reason="Marked-block reduction completed.")


def source_metrics(path: Path) -> dict[str, int]:
    data = path.read_bytes()
    return {"bytes": len(data), "lines": len(data.decode("utf-8", errors="replace").splitlines())}
