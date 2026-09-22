# PassWitness Phase 1 design

The pipeline has four trust boundaries:

1. A metadata pass independently elaborates the original RTL and records the top-level ports.
2. A synthesis pass preloads the same RTL, applies the user flow, flattens the resulting combinational candidate, and exports it under `passwitness_candidate`.
3. A formal pass loads the original RTL, the exported candidate, and a generated miter into a fresh Yosys process. The miter drives both implementations from the same inputs and proves `mismatch == 0` with `sat -verify`.
4. The verdict parser requires explicit SAT success/failure markers. Missing markers and process errors fail closed.

Generated artifacts are isolated under the requested output directory. The original RTL and flow are read-only inputs. Yosys commands are passed as argument vectors to `subprocess.run`; no shell interpolation is used by the Python runner.

The direct miter is intentionally small. EQY is the better integration point for richer sequential and partitioned equivalence workflows; integrating its core would duplicate mature functionality and would not improve the Phase 1 artifact model.
