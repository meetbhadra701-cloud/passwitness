# PassWitness

**Formal-Guided Synthesis Fault Localization and Test-Case Reduction**

PassWitness detects functional mismatches introduced during hardware synthesis, identifies the earliest verified divergent transformation, and helps reduce the failing RTL into a reproducible bug report.

PassWitness v0.1 is a small, standalone command-line tool for engineers investigating **small combinational Verilog arithmetic circuits**. It is a workflow around Yosys's existing elaboration, synthesis, and SAT capabilities; it is not a new SAT solver, parser, equivalence algorithm, or fuzzer.

## The problem

A failed final equivalence check says that the synthesized result differs from the RTL, but it does not by itself say which synthesis transition introduced the difference. A useful investigation needs the exact flow, tool identity, intermediate representations, proof result, counterexample, and enough surrounding context for another engineer to reproduce it.

## What PassWitness does

PassWitness provides an explicit investigation pipeline:

1. **Detect** — run a user-selected Yosys flow and independently elaborate the RTL reference and synthesized candidate.
2. **Localize** — capture supported RTLIL checkpoints and find the first verified `PASS -> FAIL` transition.
3. **Replay** — apply the failing checkpoint's fixed witness to the reference, preceding checkpoint, and failing checkpoint as explanatory evidence.
4. **Minimize** — use the fail-closed oracle with marked-block reduction or the optional `sv-bugpoint` adapter.
5. **Reverify** — rerun the selected contract in a fresh workspace after reduction.
6. **Package** — write machine-readable JSON, a Markdown report, logs, checkpoints, witnesses, and a relocatable evidence package.

The tool fails closed. A process exit code of zero is not a formal `PASS`; a SAT counterexample is not a pass; and a timeout, unsupported operation, missing proof marker, or setup error cannot become a successful diagnosis.

## Real Yosys defect demonstration

The checked-in `fixtures/signed_fma_bug/` design is the reduced signed wide-accumulation FMA reproducer used in the investigation. With the preserved clean Yosys build, the actual result is:

| Check | Result |
|---|---|
| Final design equivalence | `FAIL` |
| Last proven-equivalent checkpoint | `alumacc` |
| First failing transition | `arith_tree` |
| Instrumentation flow fidelity | `PASS` |
| Fixed-witness replay | `CONFIRMED` |

The corresponding patched build reports final `PASS`. The executable reports the clean base commit `e8db64c609c7ae4574e66bbd475f5f10f36d7a31`; the patched wrapper claims `30b851e63ff071578cda4e1e49eccd367f7881d9` but its source tree was not independently available to PassWitness, so that source revision is **not** marked verified.

The related upstream contribution is [Yosys PR #6231](https://github.com/YosysHQ/yosys/pull/6231). At the time of this release preparation it is **open**, not merged. PassWitness does not modify or depend on that PR being accepted.

## Installation

Requirements:

- Python 3.10 or newer.
- An external Yosys executable, such as one from the [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build), for real analyses.
- No cloud service or paid EDA license.

From a fresh checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

Install test dependencies when developing:

```sh
python -m pip install ".[test]"
```

The installed `passwitness` entry point and `python -m passwitness.cli` are equivalent command paths. Installation and an invocation from outside the source directory are covered in [the quick-start guide](docs/quickstart.md).

## Quick start

Run an ordinary correct control with any compatible Yosys executable:

```sh
passwitness analyze \
  --rtl fixtures/correct_arithmetic/source.v \
  --top correct_arithmetic \
  --flow fixtures/correct_arithmetic/synthesis.ys \
  --yosys /path/to/yosys \
  --output-dir out/correct
```

Run the known signed-FMA reproducer with the preserved clean wrapper when the validation Docker images are available:

```sh
passwitness analyze \
  --rtl fixtures/signed_fma_bug/source.v \
  --top fma_impl \
  --flow fixtures/signed_fma_bug/synthesis.ys \
  --yosys "$PWD/tools/yosys-clean" \
  --localize \
  --output-dir out/fma-clean
```

Inspect `out/fma-clean/result.json` for automation and `out/fma-clean/report.md` for the human-readable investigation. The exact preserved environment and the optional patched comparison are documented in [reproducibility](docs/reproducibility.md).

## Understanding results

The top-level formal status is separate from localization and flow fidelity:

| Status | Meaning |
|---|---|
| `PASS` | The explicit output-equivalence property was proved for the supported semantics. |
| `FAIL` | Yosys SAT produced a genuine mismatch model. |
| `TIMEOUT` | The proof or process exceeded its limit; this is not a pass. |
| `UNSUPPORTED` | The selected design, backend, cell, or flow is outside the supported contract. |
| `SETUP_ERROR` | Inputs, tools, generated scripts, or imports could not be prepared or executed. |
| `NOT_EXECUTED` | A check was deliberately not reached or was skipped after an earlier blocking result. |

`LOCALIZED` is reported only when all earlier checkpoints are proven `PASS` and the next checked checkpoint is proven `FAIL`. `INCONCLUSIVE`, an interval, or an unsupported result is used when that evidence is unavailable. `FLOW FIDELITY` is an independent comparison between the ordinary flow and the instrumented flow; a final mismatch produces `INSTRUMENTATION_MISMATCH` rather than a trusted localization.

## Failure minimization

Minimization is opt-in. The bounded built-in reducer removes complete marked blocks from the **current** candidate source, requires strict size progress, isolates every candidate, and runs the existing formal oracle against that candidate's own golden RTL.

```sh
passwitness minimize \
  --rtl fixtures/reduction_control/source.v \
  --top reduction_control \
  --flow fixtures/reduction_control/synthesis.ys \
  --yosys /path/to/yosys \
  --mode PRESERVE_LOCALIZED_FAILURE \
  --target-stage injected_constant \
  --output-dir out/reduction-control
```

The optional syntax-aware [`sv-bugpoint`](https://github.com/antmicro/sv-bugpoint) adapter invokes the same PassWitness oracle and returns success to the reducer only for a confirmed interesting candidate. It was executed against the checked-in signed-FMA reproducer in an isolated Docker build. `sv-bugpoint` is not bundled. C-Reduce and Yosys `bugpoint` were not used as interchangeable source reducers in this release.

The two measured v0.1 demonstrations are deliberately separate:

| Benchmark | Original | Reduced | Evidence |
|---|---:|---:|---|
| Signed-FMA reproducer, `sv-bugpoint` | 325 bytes / 12 lines | 305 bytes / 11 lines | Clean Yosys `FAIL`, localized to `arith_tree`; patched control `PASS`. |
| Injected arithmetic fault, marked blocks | 1110 bytes / 31 lines | 326 bytes / 15 lines | 70.63% bytes, 51.61% lines; `injected_constant`; replay `CONFIRMED`. |

These are reductions observed under bounded searches, not global-minimality claims. The larger FIR4 workspace from Experiments 4–6 was not available during Phase 4.1; the checked-in `examples/fir4.v` is a correct control under its checked-in flow and is not presented as that historical reproducer.

## Evidence and reproducibility

Every completed analysis writes `result.json` and `report.md`. A localized or verified reduction also includes the relevant RTLIL snapshots, generated scripts, logs, formal witnesses, replay data, provenance, timing, and a `portable/` or `portable-reduction/` package with relative artifact references.

The package does not include Yosys or an external reducer. Its reproduction README names the required executable and records its reported version, source-revision claim, executable hash, and verification method. Relocation of the signed-FMA package to an unrelated directory was tested successfully with the external clean Yosys dependency.

## Supported designs and flows

The v0.1 formal contract is a combinational bit-vector top with ordinary input/output ports. Widths, signedness, and port correspondence are checked from independent elaborations. The direct Yosys SAT backend proves an explicit output-mismatch property over defined input assignments.

Automatic checkpoint localization supports the version-gated `synth -top TOP -arith_tree` catalog used by the signed-FMA investigation and explicit flows divided by `# passwitness-stage: NAME` markers. Opaque user flows are still valid for ordinary final analysis, but localization is honestly reported unsupported unless PassWitness actually instrumented their transitions.

## Limitations

PassWitness v0.1 does not promise arbitrary SystemVerilog, sequential or temporal verification, memories, reset behavior, X-propagation equivalence, timing/power equivalence, arbitrary black boxes, every internal Yosys cell, automatic localization inside opaque macros, universal source reduction, or production verification of every hardware design. See [limitations](docs/limitations.md) for the exact boundary.

## Prior art

PassWitness reuses Yosys and deliberately does not duplicate the core capabilities of [EQY](https://github.com/YosysHQ/eqy), [SymbiYosys](https://github.com/YosysHQ/SymbiYosys), [Verismith](https://github.com/ymherklotz/verismith), [VlogHammer](https://github.com/YosysHQ/yosys-web/blob/master/vloghammer.in), [VeriXmith](https://github.com/icsnju/VeriXmith), or [Yosys bugpoint](https://yosyshq.readthedocs.io/projects/yosys/en/latest/using_yosys/bugpoint.html). The distinction is the engineer-facing evidence workflow: exact flow records, verified checkpoints, fail-closed verdicts, witness replay, reduction auditing, and portable packaging. See [prior-art.md](docs/prior-art.md).

## Development and testing

```sh
python -m pip install -e ".[test]"
python -m pytest -q
```

The normal GitHub Actions workflow runs unit tests on supported Python and an actual-Yosys control integration job. The historical signed-FMA regression is version-sensitive and remains a separately documented reproduction rather than an unpinned CI claim.

## License and attribution

PassWitness project code is released under the MIT License. Yosys, EQY, SymbiYosys, Verismith, VlogHammer, VeriXmith, and `sv-bugpoint` are external projects; they are not bundled or claimed as PassWitness code. See [the attribution and release audit](docs/attribution.md).
