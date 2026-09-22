# v0.1 release demonstration

This is the concise real-bug demonstration used for the release audit. It uses the checked-in signed-FMA reproducer, not the unavailable larger FIR4 workspace.

## Command

With the preserved compatible clean wrapper available:

```sh
passwitness analyze \
  --rtl fixtures/signed_fma_bug/source.v \
  --top fma_impl \
  --flow fixtures/signed_fma_bug/synthesis.ys \
  --yosys "$PWD/tools/yosys-clean" \
  --localize \
  --output-dir out/release-fma-clean
```

For the patched control, change `--yosys` to `tools/yosys-patched` and use a separate output directory.

## Observed result

The completed validation produced:

```text
FINAL DESIGN:       FAIL
FLOW FIDELITY:      PASS
LOCALIZATION:       LOCALIZED
LAST PASSING:       alumacc
FIRST FAILING:      arith_tree
WITNESS REPLAY:     CONFIRMED
PATCHED CONTROL:    PASS
```

The clean witness preserves the actual reference and candidate outputs in the generated JSON/VCD evidence. The reduced source produced by the external `sv-bugpoint` run is 305 bytes and 11 lines; its fresh clean re-verification recovered the same boundary, and its patched control passed.

The output directory contains `result.json`, `report.md`, logs, checkpoint RTLIL, formal scripts, and witnesses. The exported `portable-reduction/` package can be moved to another directory and rerun with the separately supplied Yosys executable.
