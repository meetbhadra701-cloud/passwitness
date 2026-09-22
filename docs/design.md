# PassWitness design

The pipeline has four trust boundaries:

1. A metadata pass independently elaborates the original RTL and records the top-level ports.
2. A synthesis pass preloads the same RTL, applies the user flow, flattens the resulting combinational candidate, and exports it under `passwitness_candidate`.
3. A formal pass loads the original RTL, the exported candidate, and a generated miter into a fresh Yosys process. The miter drives both implementations from the same inputs and proves `mismatch == 0` with `sat -verify`.
4. The verdict parser requires explicit SAT success/failure markers. Missing markers and process errors fail closed.

Generated artifacts are isolated under the requested output directory. The original RTL and flow are read-only inputs. Yosys commands are passed as argument vectors to `subprocess.run`; no shell interpolation is used by the Python runner.

The direct miter is intentionally small. EQY is the better integration point for richer sequential and partitioned equivalence workflows; integrating its core would duplicate mature functionality and would not improve the Phase 1 artifact model.

## Phase 2 localization

`--localize` adds a second, explicitly bounded pipeline after the ordinary Phase 1 analysis:

1. `checkpoints.py` recognizes either the exact supported `synth -top TOP -arith_tree` command or a flow containing at least two `# passwitness-stage: NAME` boundaries. For the macro flow it expands the installed Yosys sequence used by the signed-FMA investigation. For a marked flow it executes the marked commands verbatim. Unsupported opaque flows are reported as `UNSUPPORTED`.
2. The instrumented process captures RTLIL with `write_rtlil` immediately after each real boundary. It does not reconstruct intermediate state by replaying a different flow. The generated script, commands, tool identity, and missing snapshots are recorded.
3. `localizer.py` loads each RTLIL snapshot in a fresh Yosys proof process, removes only unused modules through the normal `hierarchy -top` preparation, independently loads the golden RTL, and reuses the Phase 1 verdict parser. A precise localization requires a verified `PASS` immediately before a verified `FAIL`. Timeouts, setup errors, unsupported imports, and an unverified prefix produce an interval or an explicit non-localized status.
4. The final instrumented snapshot is compared with the ordinary Phase 1 candidate. This guards against an instrumentation rewrite changing the observed flow. A failed comparison downgrades localization to `INCONCLUSIVE`.

The result schema remains version 1 for ordinary Phase 1 runs. Localized runs use schema version 2 and add `localization.checkpoints`, ordered proof records, synthesis/formal timing, proof count, final-flow comparison, and portable-package provenance. The root report preserves absolute paths for provenance; the `portable/` evidence package rewrites scripts, reports, and JSON command strings to package-relative paths.
