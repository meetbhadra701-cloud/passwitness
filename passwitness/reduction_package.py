"""Portable package generation for Phase 4 reduction evidence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def _copy(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _rewrite(value: Any, root: Path, package: Path, original: Path, reduced: Path, flow: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<external-yosys>" if key in {"executable", "yosys", "patched_yosys"} and isinstance(item, str) and item else ("<external-temporary-directory>" if key == "temporary_directory" and isinstance(item, str) and item else _rewrite(item, root, package, original, reduced, flow)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rewrite(item, root, package, original, reduced, flow) for item in value]
    if not isinstance(value, str):
        return value
    replacements = (
        (str(root), "."),
        (str(original), f"source/{original.name}"),
        (str(reduced), f"source/{reduced.name}"),
        (str(flow), f"flow/{flow.name}"),
    )
    rewritten = value
    for old, new in replacements:
        rewritten = rewritten.replace(old, new)
    return rewritten


def _rewrite_files(package: Path, root: Path, original: Path, reduced: Path, flow: Path, tool_paths: list[str]) -> None:
    replacements = (
        (str(root), "."),
        (str(original), f"source/{original.name}"),
        (str(reduced), f"source/{reduced.name}"),
        (str(flow), f"flow/{flow.name}"),
        *[(path, "<external-yosys>") for path in tool_paths if path],
    )
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".vcd", ".rtlil", ".il"}:
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


def build_reduction_package(result: dict[str, Any], *, output_dir: Path, original: Path, reduced: Path, flow: Path) -> Path:
    package = output_dir / "portable-reduction"
    package.mkdir(parents=True, exist_ok=True)
    _copy(original, package / "source" / original.name)
    _copy(reduced, package / "source" / reduced.name)
    _copy(flow, package / "flow" / flow.name)
    # The small PassWitness Python package is part of the portable reproducer;
    # the external synthesis/formal executable remains intentionally separate.
    _copy(Path(__file__).parent, package / "passwitness")
    for name in ("oracle", "reduction-work", "final-reverification"):
        _copy(output_dir / name, package / name)
    tool_paths = []
    configuration = result.get("configuration") or {}
    for key in ("yosys", "patched_yosys"):
        value = configuration.get(key)
        if value:
            tool_paths.append(str(Path(value).resolve()))
    _rewrite_files(package, output_dir, original, reduced, flow, tool_paths)
    portable = _rewrite(result, output_dir, package, original, reduced, flow)
    (package / "result.json").write_text(json.dumps(portable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = (
        "PYTHONPATH=. python3 -m passwitness.cli analyze "
        f"--rtl source/{reduced.name} --top {result.get('top_module')} --flow flow/{flow.name} "
        "--yosys /path/to/yosys --localize --output-dir replay"
    )
    readme = "\n".join([
        "# PassWitness portable reduced-failure package",
        "",
        "This package contains the original and independently reverified reduced RTL, the exact flow, reduction audit, oracle analyses, checkpoints, formal logs, and witnesses.",
        "",
        "The reducer was bounded and marker-based; no global-minimality claim is made.",
        "Install PassWitness and the recorded external Yosys dependency. The executable is intentionally not bundled.",
        "",
        "To reproduce the selected reduced analysis:",
        "",
        "```sh",
        command,
        "```",
        "",
        "All references in result.json are relative to this directory.",
        "",
    ])
    (package / "README.md").write_text(readme, encoding="utf-8")
    return package
