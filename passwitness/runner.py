from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import time
from pathlib import Path

from .backends import make_backend
from .formal import counterexample_from_model, load_ports, module_is_sequential, port_correspondence_errors, write_miter
from .models import AnalysisResult, CommandResult, FormalResult, Verdict
from .reports import write_report, write_result


_PARAMETER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_PARAMETER_VALUE = re.compile(r"^[A-Za-z0-9_$'()+*/%<>&|~^ -]+$")
_TOP_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _ys_path(path: Path) -> str:
    """Quote a path for the Yosys command language, not a shell."""
    return json.dumps(str(path))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(argv: list[str], log_path: Path, timeout: float | None, cwd: Path) -> CommandResult:
    start = time.monotonic()
    timed_out = False
    returncode: int | None = None
    try:
        completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        returncode = completed.returncode
        output = completed.stdout + ("\n" if completed.stdout and completed.stderr else "") + completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        output = (exc.stdout or "") + ("\n" if exc.stdout and exc.stderr else "") + (exc.stderr or "")
        output += "\nPassWitness: process timeout expired.\n"
    except OSError as exc:
        output = f"PassWitness could not start command: {exc}\n"
        returncode = None
    runtime = time.monotonic() - start
    _write_text(log_path, output)
    return CommandResult(argv=argv, returncode=returncode, runtime_seconds=runtime, log_path=str(log_path), timed_out=timed_out)


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def _tool_version(yosys: str, root: Path, work: Path) -> tuple[dict[str, object], str | None]:
    record = _run([yosys, "-V"], work / "tool-version.log", 30, root)
    text = Path(record.log_path).read_text(encoding="utf-8", errors="replace")
    version = next((line.strip() for line in text.splitlines() if line.strip()), "")
    reported_commit = re.search(r"git sha1 ([0-9a-fA-F]+)", text)
    claim_match = re.search(r"PassWitness source commit:\s*([0-9a-fA-F]+)", text)
    executable = Path(yosys)
    if not executable.is_file():
        resolved = shutil.which(yosys)
        executable = Path(resolved) if resolved else executable
    executable_sha256 = _sha256_file(executable) if executable.is_file() else None
    if record.returncode != 0 or not version:
        return {}, "Yosys is unavailable or did not return a version string."
    source_claim = claim_match.group(1) if claim_match else None
    return {
        # Legacy fields remain for Phase 1/2 consumers. `commit` is the
        # wrapper/source claim when one exists, not an independently verified
        # identity of the executable.
        "executable": yosys,
        "version": version,
        "commit": source_claim or (reported_commit.group(1) if reported_commit else None),
        "yosys_reported_version": version,
        "yosys_reported_commit": reported_commit.group(1) if reported_commit else None,
        "executable_sha256": executable_sha256,
        "source_revision_claim": source_claim,
        "source_revision_verified": False,
        "source_tree_dirty": None,
        "patch_sha256": None,
        "verification_method": "Yosys -V output and SHA-256 of the executable path; source checkout was not supplied",
    }, None


def _params(parameters: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in parameters:
        if "=" not in item:
            raise ValueError(f"Parameter must use NAME=VALUE syntax: {item!r}")
        name, value = item.split("=", 1)
        if not _PARAMETER_NAME.fullmatch(name) or not _PARAMETER_VALUE.fullmatch(value):
            raise ValueError(f"Unsupported parameter syntax: {item!r}")
        values[name] = value
    return values


def _parameter_commands(parameters: dict[str, str], top: str) -> str:
    return "\n".join(f"chparam -set {name} {value} {top}" for name, value in parameters.items())


def _counterexample(result: AnalysisResult, ports: list) -> dict | None:
    if result.formal.verdict != Verdict.FAIL:
        return None
    model = result.formal.model
    return counterexample_from_model(model, ports)


def analyze(
    *,
    rtl: Path,
    top: str,
    flow: Path,
    output_dir: Path,
    yosys: str = "yosys",
    parameters: list[str] | None = None,
    timeout: float = 300.0,
    localize: bool = False,
    backend_name: str = "yosys-sat",
) -> AnalysisResult:
    output_dir = output_dir.resolve()
    work = output_dir / "work"
    logs = output_dir / "logs"
    witnesses = output_dir / "witnesses"
    for directory in (work, logs, witnesses):
        directory.mkdir(parents=True, exist_ok=True)
    rtl = rtl.resolve()
    flow = flow.resolve()
    try:
        parameter_values = _params(parameters or [])
    except ValueError as exc:
        result = AnalysisResult(Verdict.SETUP_ERROR, str(rtl), top, str(flow), str(output_dir), {}, errors=[str(exc)])
        if localize:
            result.localization = {"status": "NOT_EXECUTED", "reason": "Localization was not executed because setup failed."}
        write_result(result)
        write_report(result)
        return result

    result = AnalysisResult(Verdict.NOT_EXECUTED, str(rtl), top, str(flow), str(output_dir), parameter_values)
    if localize:
        result.localization = {"status": "NOT_EXECUTED", "reason": "Localization was not executed."}
    result.paths.update({"tool_version_log": str(logs / "tool-version.log"), "synthesis_log": str(logs / "synthesis.log"), "formal_log": str(logs / "formal.log")})
    try:
        if not _TOP_NAME.fullmatch(top):
            raise ValueError(f"Unsupported top-module identifier: {top!r}")
        if not rtl.is_file():
            raise FileNotFoundError(f"RTL file does not exist: {rtl}")
        if not flow.is_file():
            raise FileNotFoundError(f"Flow file does not exist: {flow}")
        result.tool, tool_error = _tool_version(yosys, output_dir.parent, work)
        if tool_error:
            raise RuntimeError(tool_error)

        metadata = work / "golden.json"
        metadata_script = work / "golden-metadata.ys"
        _write_text(metadata_script, "\n".join([
            f"read_verilog -sv {_ys_path(rtl)}",
            f"hierarchy -top {top}",
            _parameter_commands(parameter_values, top),
            f"proc",
            f"write_json {_ys_path(metadata)}",
        ]) + "\n")
        metadata_run = _run([yosys, "-s", str(metadata_script)], logs / "golden-metadata.log", timeout, output_dir.parent)
        result.paths["golden_metadata_log"] = metadata_run.log_path
        if metadata_run.timed_out:
            result.status = Verdict.TIMEOUT
            result.errors.append("Golden-reference elaboration timed out.")
            result.unexecuted_checks.append("Candidate synthesis and formal equivalence.")
            return _finish(result)
        if metadata_run.returncode != 0 or not metadata.is_file():
            raise RuntimeError("Golden-reference elaboration failed; no trustworthy port metadata was produced.")
        ports = load_ports(metadata, top)
        if module_is_sequential(metadata, top):
            result.status = Verdict.UNSUPPORTED
            result.formal.reason = "The Phase 1 engine supports combinational designs only; sequential cells were found."
            result.unexecuted_checks.append("Synthesis and formal equivalence for a sequential design.")
            result.verified_facts.append("The RTL parsed and its top-level ports were extracted.")
            return _finish(result)

        candidate_script = work / "candidate.ys"
        candidate_netlist = work / "candidate.v"
        candidate_metadata = work / "candidate.json"
        candidate_script_text = "\n".join([
            f"read_verilog -sv {_ys_path(rtl)}",
            _parameter_commands(parameter_values, top),
            flow.read_text(encoding="utf-8"),
            "rename -top passwitness_candidate",
            f"write_verilog -noattr {_ys_path(candidate_netlist)}",
            f"write_json {_ys_path(candidate_metadata)}",
        ]) + "\n"
        _write_text(candidate_script, candidate_script_text)
        synthesis_run = _run([yosys, "-s", str(candidate_script)], logs / "synthesis.log", timeout, output_dir.parent)
        result.synthesis = {
            "script": str(candidate_script),
            "flow": str(flow),
            "runtime_seconds": synthesis_run.runtime_seconds,
            "returncode": synthesis_run.returncode,
            "log_path": synthesis_run.log_path,
        }
        result.paths["candidate_netlist"] = str(candidate_netlist)
        result.paths["candidate_metadata"] = str(candidate_metadata)
        if synthesis_run.timed_out:
            result.status = Verdict.TIMEOUT
            result.errors.append("Synthesis exceeded its configured timeout.")
            result.unexecuted_checks.append("Formal equivalence.")
            return _finish(result)
        if synthesis_run.returncode != 0 or not candidate_netlist.is_file():
            raise RuntimeError("Synthesis failed or did not produce a candidate netlist.")
        if not candidate_metadata.is_file():
            raise RuntimeError("Synthesis did not produce candidate interface metadata.")
        candidate_ports = load_ports(candidate_metadata, "passwitness_candidate")
        interface_errors = port_correspondence_errors(ports, candidate_ports)
        if interface_errors:
            raise RuntimeError("Golden/candidate port correspondence mismatch: " + "; ".join(interface_errors))

        miter = work / "miter.v"
        write_miter(miter, top, ports, parameter_values)
        formal_script = work / "formal.ys"
        cex_json = witnesses / "counterexample.json"
        cex_vcd = witnesses / "counterexample.vcd"
        formal_script_text = "\n".join([
            f"read_verilog -sv {_ys_path(rtl)}",
            f"read_verilog {_ys_path(candidate_netlist)}",
            f"read_verilog {_ys_path(miter)}",
            "hierarchy -top passwitness_miter",
            "prep -top passwitness_miter",
            "flatten",
            "opt",
            f"sat -prove mismatch 0 -verify -set-def-inputs -show-ports -dump_json {_ys_path(cex_json)} -dump_vcd {_ys_path(cex_vcd)}",
        ]) + "\n"
        _write_text(formal_script, formal_script_text)
        backend = make_backend(backend_name, yosys, output_dir.parent, timeout)
        formal_run = backend.execute(formal_script, logs / "formal.log")
        verdict, reason = formal_run.verdict, formal_run.reason
        result.formal = FormalResult(
            verdict=verdict,
            reason=reason,
            runtime_seconds=formal_run.runtime_seconds,
            log_path=formal_run.log_path,
            counterexample_json=str(cex_json) if cex_json.is_file() else None,
            counterexample_vcd=str(cex_vcd) if cex_vcd.is_file() else None,
            model=formal_run.model,
            backend=backend.name,
        )
        result.status = verdict
        result.paths.update({"miter": str(miter), "formal_script": str(formal_script)})
        result.verified_facts.extend([
            f"Yosys version recorded as {result.tool.get('version', 'unknown')}.",
            f"Formal backend: {backend.name}.",
            "The golden RTL and synthesized candidate were independently loaded into a generated output-comparison miter.",
            f"Formal classification is {verdict.value} based on an explicit SAT proof marker.",
        ])
        result.counterexample = _counterexample(result, ports)
        if verdict == Verdict.PASS:
            result.inferences.append("The tested combinational input space is equivalent under the supplied flow.")
        elif verdict == Verdict.FAIL:
            result.inferences.append("The candidate differs from the golden RTL for at least one input assignment.")
        elif verdict == Verdict.TIMEOUT:
            result.unexecuted_checks.append("A completed equivalence proof.")
        else:
            result.unexecuted_checks.append("A trustworthy functional verdict.")
        if localize:
            from .localizer import localize as run_localization

            result.localization = run_localization(
                result=result,
                rtl=rtl,
                top=top,
                flow=flow,
                output_dir=output_dir,
                yosys=yosys,
                parameters=parameter_values,
                timeout=timeout,
                ports=ports,
                normal_candidate=candidate_netlist,
                backend=backend,
            )
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        result.status = Verdict.SETUP_ERROR
        result.errors.append(str(exc))
        result.formal = FormalResult(verdict=Verdict.NOT_EXECUTED, reason="Formal check was not executed because setup failed.")
        result.unexecuted_checks.append("Formal equivalence.")
    return _finish(result)


def _finish(result: AnalysisResult) -> AnalysisResult:
    write_result(result)
    write_report(result)
    if result.localization and result.localization.get("portable_package"):
        from .package import build_portable_package

        package = build_portable_package(result)
        result.paths["portable_package"] = str(package)
        write_result(result)
        write_report(result)
        build_portable_package(result)
    return result
