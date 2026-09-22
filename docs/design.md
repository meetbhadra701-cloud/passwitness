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

The result schema remains version 1 for ordinary Phase 1 runs. Localized Phase 2 results use schema version 2; Phase 3 localized results use schema version 3 and add flow fidelity, backend, provenance, and replay records. The root report preserves absolute paths for provenance; the `portable/` evidence package rewrites scripts, reports, and JSON command strings to package-relative paths.

## Phase 3 fidelity and evidence

The exact `synth -top TOP -arith_tree` catalog is version-gated to the observed Yosys `0.69+` implementation. Its expansion follows the installed `help synth` command groups: `begin`, `coarse`, `fine`, and `check`; it does not silently add `flatten` or omit options. Other versions must use explicit stage markers unless a new catalog is added from their documented behavior. Marked flows are executed as written, with only `write_rtlil` checkpoint commands added.

Every localized result records original commands, instrumented commands, added commands, expansion records, ordered checkpoint commands, selected options, tool version, and both final representations. The original synthesis run remains the source of the ordinary final candidate. A final comparison against the instrumented RTLIL is reported separately as flow fidelity. A `FAIL` comparison is `INSTRUMENTATION_MISMATCH`; a timeout or setup failure cannot support a trusted localization.

The direct Yosys SAT backend proves `mismatch == 0` over defined combinational bit-vector inputs. Port widths and signedness come from independently elaborated Yosys JSON metadata; candidate/golden port correspondence is checked explicitly before formal proof. Undefined input bits, missing drivers, combinational loops, black boxes, unsupported internal cells, sequential elements, and memories are not silently coerced into a supported semantic. Yosys SAT fixed-input replay is separate explanatory evidence and is never substituted for a universal proof. EQY has an adapter interface and can be selected with `--backend eqy`, but the Phase 3 adapter returns `UNSUPPORTED`; no EQY proof is claimed unless a future adapter actually runs.

Tool provenance distinguishes the version and commit reported by Yosys, a wrapper or configuration source-revision claim, the SHA-256 of the executable actually invoked, and whether a source checkout was independently available. The current Docker wrappers provide a source-revision claim; they do not independently verify the patched source tree, so `source_revision_verified` remains false.
