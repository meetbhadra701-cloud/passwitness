# Quick start

This guide uses a fresh environment and an external Yosys executable. PassWitness does not install Yosys for you.

## Install

```sh
git clone <your-passwitness-checkout>
cd passwitness
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

Check the installed entry point from outside the checkout:

```sh
cd /tmp
passwitness --help
```

Use `python -m pip install ".[test]"` instead when developing the project.

## Correct control

From the repository root, with Yosys available as `/path/to/yosys`:

```sh
passwitness analyze \
  --rtl fixtures/correct_arithmetic/source.v \
  --top correct_arithmetic \
  --flow fixtures/correct_arithmetic/synthesis.ys \
  --yosys /path/to/yosys \
  --output-dir /tmp/passwitness-correct
```

The command writes `result.json`, `report.md`, logs, and generated formal artifacts below the requested directory. The expected final status is `PASS` for a compatible Yosys.

## Known signed-FMA demonstration

The exact historical result is version-sensitive. The repository's `tools/yosys-clean` and `tools/yosys-patched` wrappers refer to the preserved validation Docker images and are not general Yosys installers:

```sh
passwitness analyze \
  --rtl fixtures/signed_fma_bug/source.v \
  --top fma_impl \
  --flow fixtures/signed_fma_bug/synthesis.ys \
  --yosys "$PWD/tools/yosys-clean" \
  --localize \
  --output-dir out/fma-clean
```

The recorded validation result is `FAIL`, with `alumacc` as the last passing checkpoint and `arith_tree` as the first failing transition. The same fixture with the preserved patched wrapper reports final `PASS`. See [reproducibility.md](reproducibility.md) for tool identity, hashes, and the patched-source provenance caveat.

## Read the result

```sh
python -m json.tool out/fma-clean/result.json
less out/fma-clean/report.md
```

Do not infer a pass from a zero process return code. Read the structured status and the formal reason. `FAIL` must contain a genuine counterexample; `TIMEOUT`, `UNSUPPORTED`, and `SETUP_ERROR` are not functional failures and cannot be promoted to successful localization.

## Localize and reduce

Add `--localize` to an ordinary analysis when the flow is the supported `synth -arith_tree` catalog or contains explicit `# passwitness-stage: NAME` markers. For the marked-block reducer:

```sh
passwitness minimize \
  --rtl fixtures/reduction_control/source.v \
  --top reduction_control \
  --flow fixtures/reduction_control/synthesis.ys \
  --yosys /path/to/yosys \
  --mode PRESERVE_LOCALIZED_FAILURE \
  --target-stage injected_constant \
  --output-dir /tmp/passwitness-reduction
```

The reducer stores candidate sources and an audit trail. It requires strict size progress by default and independently re-verifies the final candidate. The result is not a global-minimality claim.

## Missing Yosys

If the executable is missing or cannot report a version, PassWitness writes a `SETUP_ERROR` result and does not attempt to reinterpret it as a formal result.
