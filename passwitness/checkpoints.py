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
    original_commands: list[str] | None = None
    instrumented_commands: list[str] | None = None
    added_commands: list[str] | None = None
    expanded_commands: list[dict[str, object]] | None = None
    execution_order: list[dict[str, object]] | None = None
    selected_options: dict[str, object] | None = None
    catalog_id: str | None = None
    tool_version: str | None = None


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


def _execution_order(specs: list[CheckpointSpec]) -> list[dict[str, object]]:
    return [
        {
            "index": index,
            "name": spec.name,
            "transition": spec.transition,
            "commands": spec.capture_commands,
            "snapshot": str(spec.snapshot_path),
        }
        for index, spec in enumerate(specs)
    ]


def _flow_commands(flow: Path) -> list[str]:
    try:
        return [line.strip() for line in flow.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
    except (OSError, UnicodeError):
        return []


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
        if current is None and line.strip() and not line.strip().startswith("#"):
            # A marked plan cannot silently drop an unmarked command before
            # its first checkpoint boundary.
            return None
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


def build_instrumented_flow(
    flow: Path,
    top: str,
    work_dir: Path,
    rtl: Path,
    parameters: dict[str, str],
    *,
    tool_version: str | None = None,
) -> InstrumentedFlow:
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
            original_commands=_flow_commands(flow),
            tool_version=tool_version,
        )
    if macro is not None:
        if tool_version is None or "0.69" not in tool_version:
            return InstrumentedFlow(
                supported=False,
                reason=(
                    "The exact synth -arith_tree expansion is cataloged only for the observed Yosys 0.69 build; "
                    "use explicit passwitness-stage markers for another Yosys version."
                ),
                mode="unsupported_version",
                original_commands=_flow_commands(flow),
                selected_options={"top": top, "arith_tree": True},
                catalog_id="yosys-0.69-synth-arith-tree",
                tool_version=tool_version,
            )
        specs, commands = _macro_plan(top, checkpoint_dir)
        mode = "synth_arith_tree_expansion"
        original_commands = _flow_commands(flow)
        expanded = [{"original": original_commands, "replacement": commands}]
        selected_options = {"top": top, "arith_tree": True}
        catalog_id = "yosys-0.69-synth-arith-tree"
    else:
        specs, commands = marked  # type: ignore[misc]
        mode = "marked_explicit_flow"
        original_commands = _flow_commands(flow)
        expanded = []
        selected_options = {"top": top, "marked_boundaries": [spec.name for spec in specs]}
        catalog_id = "explicit-marked-flow"
    script_path = work_dir / "instrumented-flow.ys"
    header = [f"read_verilog -sv {_ys_path(rtl)}"]
    header.extend(f"chparam -set {name} {value} {top}" for name, value in parameters.items())
    script_path.write_text("\n".join(header + commands) + "\n", encoding="utf-8")
    added = [command for spec in specs for command in spec.capture_commands if command.startswith("write_rtlil ")]
    return InstrumentedFlow(
        supported=True,
        reason="",
        mode=mode,
        script_path=script_path,
        stages=specs,
        final_snapshot=specs[-1].snapshot_path,
        commands=header + commands,
        original_commands=original_commands,
        instrumented_commands=header + commands,
        added_commands=added,
        expanded_commands=expanded,
        execution_order=[
            {"index": -1, "name": "load", "transition": "elaboration", "commands": header, "snapshot": None},
            *(_execution_order(specs)),
        ],
        selected_options=selected_options,
        catalog_id=catalog_id,
        tool_version=tool_version,
    )
