"""Create a self-contained, relative-path evidence package."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .models import AnalysisResult


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _rewrite_text_files(package_dir: Path, output_dir: Path, rtl: Path, flow: Path) -> None:
    """Make copied scripts and logs usable without the original checkout path."""
    replacements = (
        (str(output_dir), "."),
        (str(rtl), f"source/{rtl.name}"),
        (str(flow), f"flow/{flow.name}"),
    )
    for path in package_dir.rglob("*"):
        if not path.is_file() or path.name.endswith((".vcd", ".il")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        rewritten = text
        for old, new in replacements:
            rewritten = rewritten.replace(old, new)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")


def _rewrite(value: Any, output_dir: Path, package_dir: Path, rtl: Path, flow: Path) -> Any:
    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            if key == "executable" and isinstance(item, str):
                rewritten[key] = "<external-yosys>"
            else:
                rewritten[key] = _rewrite(item, output_dir, package_dir, rtl, flow)
        return rewritten
    if isinstance(value, list):
        return [_rewrite(item, output_dir, package_dir, rtl, flow) for item in value]
    if not isinstance(value, str):
        return value
    # Commands are stored as strings containing paths, so handle embedded
    # provenance paths before treating the value as a standalone path.
    embedded = value.replace(str(output_dir), ".")
    embedded = embedded.replace(str(rtl), f"source/{rtl.name}")
    embedded = embedded.replace(str(flow), f"flow/{flow.name}")
    if embedded != value:
        return embedded
    if value == str(output_dir):
        return "."
    if value == str(rtl):
        return f"source/{rtl.name}"
    if value == str(flow):
        return f"flow/{flow.name}"
    try:
        relative = Path(value).resolve().relative_to(output_dir.resolve())
    except (ValueError, OSError):
        return value
    return relative.as_posix()


def build_portable_package(result: AnalysisResult) -> Path:
    output_dir = Path(result.output_dir)
    package_dir = output_dir / "portable"
    package_dir.mkdir(parents=True, exist_ok=True)
    rtl = Path(result.rtl)
    flow = Path(result.flow)
    source_dir = package_dir / "source"
    flow_dir = package_dir / "flow"
    source_dir.mkdir(parents=True, exist_ok=True)
    flow_dir.mkdir(parents=True, exist_ok=True)
    if rtl.is_file():
        shutil.copy2(rtl, source_dir / rtl.name)
    if flow.is_file():
        shutil.copy2(flow, flow_dir / flow.name)
    for name in ("checkpoints", "logs", "witnesses", "work", "localization"):
        _copy_tree(output_dir / name, package_dir / name)

    _rewrite_text_files(package_dir, output_dir, rtl, flow)

    portable_result = _rewrite(result.to_dict(), output_dir, package_dir, rtl, flow)
    (package_dir / "result.json").write_text(json.dumps(portable_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = output_dir / "report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else "# PassWitness report\n"
    replacements = {
        str(output_dir): ".",
        str(rtl): f"source/{rtl.name}",
        str(flow): f"flow/{flow.name}",
    }
    for old, new in replacements.items():
        report = report.replace(old, new)
    (package_dir / "report.md").write_text(report, encoding="utf-8")
    command = (
        "passwitness analyze "
        f"--rtl source/{rtl.name} --top {result.top} --flow flow/{flow.name} "
        f"--yosys /path/to/yosys --localize --output-dir replay"
    )
    readme = "\n".join([
        "# PassWitness portable evidence package",
        "",
        "This directory contains the RTL, flow, generated checkpoints, formal scripts, logs, witnesses, result, and report from one investigation.",
        "",
        "External tools are intentionally not bundled. Install the recorded Yosys version/source commit separately.",
        "",
        "A reproduction command is:",
        "",
        "```sh",
        command,
        "```",
        "",
        "The paths in result.json and report.md are relative to this package.",
        "",
    ])
    (package_dir / "README.md").write_text(readme, encoding="utf-8")
    return package_dir
