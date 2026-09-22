# Phase 4 reduction contract

## Oracle

`ReductionOracle` accepts a candidate only when the candidate is copied into an
isolated evaluation directory, parses as supported RTL, and passes the existing
Phase 3 contract. The candidate itself is independently elaborated as the
golden reference. The original unreduced RTL is never used as the candidate's
functional reference.

The oracle requires a genuine final `FAIL`, a preserved counterexample, flow
fidelity `PASS`, and fixed-witness replay `CONFIRMED`. In localized mode it also
requires the explicitly selected previous checkpoint to be `PASS`, the target
checkpoint to be `FAIL`, and the first verified transition to equal the target.
`PASS`, `TIMEOUT`, `UNSUPPORTED`, `SETUP_ERROR`, missing evidence,
instrumentation mismatch, and incorrect localization all reject a candidate.

## Reducer boundary

At the original Phase 4 baseline the environment did not contain C-Reduce or
`sv-bugpoint`. Yosys `bugpoint` is documented for minimizing designs that make
Yosys crash and does not provide the formal failure-preservation contract
required here. PassWitness therefore added a small, auditable marked-block
reducer as the in-tree path. It is not a Verilog parser, does not claim general
source reduction, and does not claim global minimality. Phase 4.1 later added
the optional `sv-bugpoint` adapter; it invokes this same oracle rather than
replacing it. C-Reduce remains unintegrated.

The search exposes runtime, evaluation-count, per-candidate timeout, temporary
directory, and parallelism controls. The implementation intentionally caps
parallelism at one so candidate artifacts and audit ordering remain
deterministic; requesting a higher cap is a setup error rather than silently
running concurrently.

## Re-verification and packaging

The final retained candidate is copied to a separate oracle root and checked
again after the search. Only that result can carry `verification_status:
VERIFIED_REDUCTION`. The portable package contains original and reduced RTL,
the exact flow, audit history, isolated oracle output, formal logs, RTLIL
checkpoints, witnesses, and a reproduction README. External Yosys is recorded
by version and executable hash but is not bundled.

The package is portable with respect to the original PassWitness checkout:
copied scripts and JSON/log text are rewritten to relative paths. The external
Yosys executable remains an explicit dependency, as required for reproducible
tool provenance.
