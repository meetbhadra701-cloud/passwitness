# Reproducible tool environments

PassWitness does not download tools or contact a service at runtime. Point `--yosys` at a system Yosys, an OSS CAD Suite `bin/yosys`, or a wrapper/container entrypoint.

For the exact signed-FMA validation performed in this workspace, `tools/yosys-clean` and `tools/yosys-patched` use the preserved Docker images `muxwise-yosys-current:exp6` and `muxwise-yosys-patched:exp6`. The wrappers also emit the source commits into the recorded tool-version log:

```text
e8db64c609c7ae4574e66bbd475f5f10f36d7a31
30b851e63ff071578cda4e1e49eccd367f7881d9
```

An engineer without those local images can build Yosys from the corresponding upstream checkout, or use an OSS CAD Suite build for ordinary PassWitness investigations. The expected signed-FMA result is version-sensitive: use the clean and patched identities above when comparing against the Phase 1 acceptance evidence. The PassWitness repository itself contains the RTL fixture, flow, generated miter algorithm, and negative controls; it does not depend on the original Experiment 1–6 directories.
