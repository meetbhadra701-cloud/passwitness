# Phase 4.1 reducer hardening

The original Phase 4 reducer parsed marker spans once from the original source
and then applied those line offsets to shortened candidates. After an earlier
block was accepted, later offsets pointed into unrelated module text. The
result was a malformed candidate such as a module header fragment.

The reducer now rescans the current candidate before every proposal, matches
the selected block by its identifier, rejects duplicate identifiers and
malformed/nested markers, and preserves all unrelated text. Acceptance also
requires strict byte-size progress in addition to an oracle-positive formal
failure. Equal-size and duplicate candidates are rejected.

The audit distinguishes total proposals, unique hashes, actual oracle
executions, cache hits, oracle-positive candidates, unique accepted candidates,
strict improvements, rejections, baseline validation, and independent final
verification. Reports include both byte and line metrics.

## External reducer adapter

The repository includes `passwitness.sv_bugpoint_check`, an interestingness
adapter for `sv-bugpoint`. It returns zero only for an accepted existing
`ReductionOracle` result; all setup, timeout, unsupported, fidelity, replay,
and localization failures return nonzero. The source candidate is passed to
the normal PassWitness oracle and is compared with its own independently
elaborated golden reference.

`sv-bugpoint` is syntax-aware SystemVerilog reduction backed by Slang. Its
documented build uses CMake and fetches/builds dependencies; its check script
takes source paths and returns zero only while the selected property remains
true. C-Reduce is for C/C++ and was not present in the environment. Yosys
`bugpoint` was also not used as a substitute because its runner contract is
not the PassWitness formal-localization contract.

The exact build and execution outcome must be recorded per environment. A
successful binary build alone is not an integration result; a real check-script
invocation must execute the PassWitness oracle.
