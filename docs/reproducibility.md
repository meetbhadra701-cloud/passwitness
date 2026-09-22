# Reproducible tool environments

PassWitness does not download tools or contact a service at runtime. Point `--yosys` at a system Yosys, an OSS CAD Suite `bin/yosys`, or a wrapper/container entrypoint. Outputs are isolated below the requested directory.

## Signed-FMA validation identities

The exact signed-FMA validation used for the v0.1 evidence used Yosys 0.69+ builds with these source-revision claims:

```text
clean:   e8db64c609c7ae4574e66bbd475f5f10f36d7a31
patched: 30b851e63ff071578cda4e1e49eccd367f7881d9
```

The clean wrapper reported `Yosys 0.69+ (git sha1 e8db64c60, Release, Clang /usr/bin/clang++ 18.1.3)` and executable SHA-256 `7d58111d6119006406e3ba635cb646da07abd48f248a0fc2899a8037630883c6` in the independent reduction recheck. The patched wrapper reported the same base Yosys version string and executable SHA-256 `3e8fe8cb6f4d76d35f30063e56057fca8593431f4daf835d1b72e232ab08af09`. The patched source checkout was not independently supplied, so the patched source revision remains a claim, not a verified field.

`tools/yosys-clean` and `tools/yosys-patched` refer to the preserved validation images `muxwise-yosys-current:exp6` and `muxwise-yosys-patched:exp6`. Those images and binaries are intentionally not bundled. An engineer without them must rebuild equivalent Yosys revisions or treat the historical comparison as unavailable; an arbitrary newer Yosys version is not expected to reproduce the defect.

To rebuild the comparison independently, check out the clean revision from
[YosysHQ/yosys](https://github.com/YosysHQ/yosys) and the patched revision from
the source branch shown by [PR #6231](https://github.com/YosysHQ/yosys/pull/6231),
then build each checkout using Yosys's documented build procedure. Pass the two
resulting executables separately with `--yosys`. PassWitness records the
reported version and executable hash; it marks the source revision verified
only when the source checkout is independently supplied to the provenance
workflow. This source rebuild path is documented for reproducibility, but the
release audit's executed comparison used the preserved Docker images above.

## Public demonstration facts

The checked-in signed-FMA reproducer is 325 bytes and 12 lines. The executed `sv-bugpoint` reduction produced 305 bytes and 11 lines. A fresh clean-Yosys re-verification reported `FAIL`, last passing checkpoint `alumacc`, first failing checkpoint `arith_tree`, flow fidelity `PASS`, and witness replay `CONFIRMED`. The corresponding patched control reported `PASS`.

The larger FIR4 source from Experiments 4–6 was unavailable during Phase 4.1. The checked-in `examples/fir4.v` is a separate passing control under its checked-in flow and is not used as the public real-bug reduction claim.

## External reducer audit

`creduce` and `sv-bugpoint` were not installed on the host. `sv-bugpoint` was built and executed in an isolated Docker environment from revision `0e976dc6a9c47912ffbe872c999424f2f493f13e`; the resulting executable SHA-256 was `25071a6982c56c58a37712cc9628a20d869b02a8a02d94d7de273d484242cf4c`. The real adapter run invoked the PassWitness oracle 27 times, accepted 3 oracle-positive candidates, and produced the strict final reduction from 325 bytes/12 lines to 305 bytes/11 lines. The external binary is not part of this repository or its Python package.

## Relocated evidence packages

A localized run creates `portable/`; a verified reduction creates `portable-reduction/`. The package contains source RTL, the synthesis flow, relevant RTLIL checkpoints, formal and replay scripts/logs, witnesses, result, report, and a reproduction README with relative artifact references. It does not contain Yosys or claim that the original executable path is portable.

The signed-FMA reduction package was copied to an unrelated directory and rerun with the external clean Yosys dependency. It recovered `FAIL`, `arith_tree` localization, flow-fidelity `PASS`, and replay `CONFIRMED`, without the original workspace path. If the external executable is missing, PassWitness reports `SETUP_ERROR`; the package is not labeled reproduced.
