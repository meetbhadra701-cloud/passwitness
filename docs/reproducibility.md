# Reproducible tool environments

PassWitness does not download tools or contact a service at runtime. Point `--yosys` at a system Yosys, an OSS CAD Suite `bin/yosys`, or a wrapper/container entrypoint.

For the exact signed-FMA validation performed in this workspace, `tools/yosys-clean` and `tools/yosys-patched` use the preserved Docker images `muxwise-yosys-current:exp6` and `muxwise-yosys-patched:exp6`. The wrappers also emit the source commits into the recorded tool-version log:

```text
e8db64c609c7ae4574e66bbd475f5f10f36d7a31
30b851e63ff071578cda4e1e49eccd367f7881d9
```

An engineer without those local images can build Yosys from the corresponding upstream checkout, or use an OSS CAD Suite build for ordinary PassWitness investigations. The expected signed-FMA result is version-sensitive: use the clean and patched identities above when comparing against the Phase 1 acceptance evidence. The PassWitness repository itself contains the RTL fixture, flow, generated miter algorithm, and negative controls; it does not depend on the original Experiment 1–6 directories.

## Relocated evidence packages

A localized run creates `portable/`. It contains the source RTL, synthesis flow, RTLIL checkpoints, formal and replay scripts/logs, witnesses, result, report, and a README. The package does not contain Yosys or claim that the original executable path is portable. Install or provide an external Yosys executable separately, then run the README command from the package directory. The package records an executable hash and reported/source-claim provenance so a reproduction can compare tool identity.

The Phase 3 integration test copies this directory to an unrelated temporary directory and reruns the clean-Yosys investigation using only the copied RTL/flow plus the external Yosys executable. The expected result is still `FAIL` with `arith_tree` localization. If the external executable is missing, PassWitness reports `SETUP_ERROR`; the package is not labeled reproduced.
