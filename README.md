# PassWitness

PassWitness is a small, standalone command-line correctness debugger for synthesis flows. Phase 1 supports small combinational Verilog arithmetic designs. It runs a user-supplied Yosys flow, independently elaborates the RTL golden reference and generated candidate, and proves an explicit output-comparison miter with Yosys SAT.

The tool is deliberately fail-closed. `PASS` requires the explicit Yosys SAT success marker. A SAT model is `FAIL`; timeouts, setup errors, unsupported sequential designs, and missing proof markers are never reported as `PASS`.

## Install

PassWitness has no runtime Python dependencies. With Python 3.10 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

You also need a Yosys executable. An OSS CAD Suite installation is sufficient. `eqy` and `sby` are useful surrounding tools but are not required by the Phase 1 engine.

## First use

The flow is applied to an already-loaded RTL design. It should synthesize the named top and leave that design selected; it should not read the RTL itself.

```sh
passwitness analyze \
  --rtl examples/fir4.v \
  --top fir4 \
  --flow examples/synthesis.ys \
  --output-dir out/fir4
```

The command creates `result.json`, `report.md`, Yosys logs, generated scripts, the candidate netlist, and SAT witnesses below the output directory. A functional failure returns exit code 1. Setup errors return 4, timeouts 2, and unsupported designs 3.

## Reproducing the signed-FMA finding

The checked-in fixture is the minimized signed wide-accumulation reproducer from the investigation. The clean and patched Yosys builds used in the validation are available as Docker images in the original experiment environment. The repository includes wrappers for those images:

```sh
python -m passwitness.cli analyze \
  --rtl fixtures/signed_fma_bug/source.v \
  --top fma_impl \
  --flow fixtures/signed_fma_bug/synthesis.ys \
  --yosys "$PWD/tools/yosys-clean" \
  --output-dir out/fma-clean

python -m passwitness.cli analyze \
  --rtl fixtures/signed_fma_bug/source.v \
  --top fma_impl \
  --flow fixtures/signed_fma_bug/synthesis.ys \
  --yosys "$PWD/tools/yosys-patched" \
  --output-dir out/fma-patched
```

The expected verdicts are `FAIL` for clean Yosys commit `e8db64c609c7ae4574e66bbd475f5f10f36d7a31` and `PASS` for patched build `30b851e63ff071578cda4e1e49eccd367f7881d9`. The wrappers require Docker Desktop and the locally preserved images; an ordinary Yosys binary can be used with `--yosys` for other flows.

## Prior art and workflow boundary

PassWitness reuses Yosys for Verilog elaboration, synthesis, netlist export, and SAT solving. It can be used alongside EQY, which is the established equivalence-checking engine for larger and more general workflows; Phase 1 uses a direct Yosys miter so it can preserve simple input/output witnesses and keep the command self-contained. SymbiYosys remains the orchestration layer for temporal proofs. Verismith, VlogHammer, and VeriXmith address generation and fuzzing-oriented exploration. Yosys bugpoint helps localize compiler reductions. PassWitness is the reproducible engineer-facing investigation wrapper: it records the exact flow, tool identity, generated candidate, formal logs, explicit verdict, and counterexample artifacts in one directory. It is not a parser, SAT solver, fuzzer, or replacement for EQY.

## Scope and limitations

Phase 1 accepts Verilog designs that elaborate to a combinational top with ordinary input and output ports. Sequential logic, memories, inouts, multi-clock behavior, SystemVerilog language coverage beyond the installed Yosys frontend, arbitrary black boxes, and automatic stage localization are out of scope. The user flow is trusted to select the intended top and perform synthesis; PassWitness verifies the resulting candidate, not the quality of the synthesis strategy.

The formal check proves bit-vector output equivalence under defined input assignments. It does not prove analog behavior, timing, power, reset behavior, X-propagation policy, or a sequential trace property.

## Development

```sh
python -m pytest
```

The negative controls cover identical designs, deliberately incorrect arithmetic, timeout classification, missing tools, malformed RTL, and the historical false-PASS log. `tools/fake-yosys-timeout` is only a test helper for exercising the process-timeout path. Docker is optional for unit tests and required only for the exact preserved clean/patched Yosys reproduction in this workspace.
