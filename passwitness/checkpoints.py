"""Supported, state-preserving synthesis checkpoint plans."""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path


_STAGE_MARKER = re.compile(r"^\s*#\s*passwitness-stage\s*:\s*([A-Za-z0-9_.-]+)\s*$", re.I)


@dataclass
class CheckpointSpec:
    name: str
    transition: str
    snapshot_path: Path
    candidate_module: str
    capture_commands: list[str]


@dataclass
class InstrumentedFlow:
    supported: bool
    reason: str
    mode: str
    script_path: Path | None = None
    stages: list[CheckpointSpec] | None = None
    final_snapshot: Path | None = None
    commands: list[str] | None = None


def _ys_path(path: Path) -> str:
    return json.dumps(str(path))


def _strip_blank_and_comments(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def _macro_options(flow: Path, top: str) -> list[str] | None:
    try:
        tokens = shlex.split("\n".join(_strip_blank_and_comments(flow.read_text(encoding="utf-8"))), comments=True)
    except (OSError, UnicodeError, ValueError):
        return None
    if tokens == ["synth", "-top", top, "-arith_tree"]:
        return []
    return None


def _macro_plan(top: str, checkpoint_dir: Path) -> tuple[list[CheckpointSpec], list[str]]:
    """Expand the installed Yosys synth -arith_tree sequence verbatim.

    The command order follows `help synth` for the Yosys build under test and
    the stage-isolation sequence used in Experiments 4-6. The snapshot is
    written immediately after the named boundary, before any later pass.
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    specs: list[CheckpointSpec] = []
    commands: list[str] = []

    def add(name: str, transition: str, command_block: list[str]) -> None:
        snapshot = checkpoint_dir / f"{len(specs):03d}_{name}.rtlil"
        commands.extend(command_block)
        capture = f"write_rtlil {_ys_path(snapshot)}"
        commands.append(capture)
        specs.append(CheckpointSpec(name, transition, snapshot, top, command_block + [capture]))

    add("elaborated", "elaboration", [f"hierarchy -check -top {top}"])
    add("proc", "proc", ["proc", "check"])
    add(
        "opt",
        "opt",
        [
            "flatten",
            "opt_expr",
            "check",
            "opt_clean",
            "opt -nodffe -nosdff",
            "fsm",
            "opt",
        ],
    )
    add("wreduce", "wreduce", ["wreduce", "peepopt", "opt_clean"])
    add("alumacc", "alumacc", ["alumacc"])
    add("arith_tree", "arith_tree", ["arith_tree"])
    add(
        "techmap",
        "techmap",
        [
            "share",
            "opt",
            "memory -nomap",
            "opt_clean",
            "opt -fast -full",
            "memory_map",
            "opt -full",
            "techmap",
            "opt -fast",
        ],
    )
    add("abc", "abc", ["abc", "opt -fast", "hierarchy -check", "stat", "check"])
    return specs, commands


def _marked_plan(flow: Path, checkpoint_dir: Path, top: str) -> tuple[list[CheckpointSpec], list[str]] | None:
    try:
        text = flow.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    blocks: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in text.splitlines():
        marker = _STAGE_MARKER.match(line)
        if marker:
            if current is not None:
                blocks.append(current)
            current = (marker.group(1), [])
            continue
        if current is not None:
            current[1].append(line)
    if current is not None:
        blocks.append(current)
    if len(blocks) < 2:
        return None
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    specs: list[CheckpointSpec] = []
    commands: list[str] = []
    for index, (name, lines) in enumerate(blocks):
        command_block = [line for line in lines if line.strip()]
        snapshot = checkpoint_dir / f"{index:03d}_{name}.rtlil"
        commands.extend(command_block)
        capture = f"write_rtlil {_ys_path(snapshot)}"
        commands.append(capture)
        transition = "elaboration" if index == 0 else name
        specs.append(CheckpointSpec(name, transition, snapshot, top, command_block + [capture]))
    return specs, commands


def build_instrumented_flow(flow: Path, top: str, work_dir: Path, rtl: Path, parameters: dict[str, str]) -> InstrumentedFlow:
    """Return a plan only for flows whose boundaries are actually observable."""
    checkpoint_dir = work_dir / "checkpoints"
    macro = _macro_options(flow, top)
    marked = _marked_plan(flow, checkpoint_dir, top) if macro is None else None
    if macro is None and marked is None:
        return InstrumentedFlow(
            supported=False,
            reason=(
                "Localization supports either the exact `synth -top TOP -arith_tree` flow "
                "or a flow with at least two `# passwitness-stage: NAME` blocks."
            ),
            mode="unsupported",
        )
    if macro is not None:
        specs, commands = _macro_plan(top, checkpoint_dir)
        mode = "synth_arith_tree_expansion"
    else:
        specs, commands = marked  # type: ignore[misc]
        mode = "marked_explicit_flow"
    script_path = work_dir / "instrumented-flow.ys"
    header = [f"read_verilog -sv {_ys_path(rtl)}"]
    header.extend(f"chparam -set {name} {value} {top}" for name, value in parameters.items())
    script_path.write_text("\n".join(header + commands) + "\n", encoding="utf-8")
    return InstrumentedFlow(
        supported=True,
        reason="",
        mode=mode,
        script_path=script_path,
        stages=specs,
        final_snapshot=specs[-1].snapshot_path,
        commands=header + commands,
    )
