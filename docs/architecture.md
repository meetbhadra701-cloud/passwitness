# PassWitness architecture

PassWitness is a deliberately narrow investigation pipeline. The source RTL and user flow remain read-only inputs; generated scripts, logs, checkpoints, and reports are written below the selected output directory.

```text
CLI
 ├─ runner ─────────────── ordinary synthesis and final candidate
 │    └─ formal backends ─ independent golden/candidate miter and verdict
 ├─ checkpoints ───────── actual instrumented RTLIL boundaries
 │    └─ localizer ─────── ordered checkpoint proofs and PASS→FAIL evidence
 ├─ witness replay ────── fixed-input explanatory comparisons
 ├─ reduction oracle ──── candidate validation and selected failure contract
 │    └─ reducers ─────── marked blocks or sv-bugpoint adapter
 ├─ reports/models ────── schema-versioned JSON and Markdown
 └─ package ───────────── relative-path portable evidence package
```

## Trust boundaries

1. The runner independently elaborates the original RTL to collect the top-level interface, then runs the selected synthesis flow to produce a candidate.
2. The formal layer loads the golden RTL and candidate representation into a fresh Yosys process and proves an explicit output mismatch property. The candidate is never reused as its own golden reference.
3. The verdict classifier requires the actual SAT success marker for `PASS`. Process success alone is insufficient.
4. The checkpoint generator captures RTLIL with `write_rtlil` at supported boundaries from the actual controlled pass sequence. It does not invent an intermediate state by replaying an unrelated flow.
5. The localizer checks checkpoints in order and reports a precise boundary only when every earlier required result is `PASS` and the next result is `FAIL`. Timeouts, setup errors, unsupported imports, missing snapshots, and unverified prefixes remain inconclusive.
6. Flow fidelity compares the ordinary final candidate with the instrumented final representation. A mismatch is reported separately and prevents a trusted localization.
7. Witness replay is explanatory evidence for one fixed input. It is stored separately and never replaces a universal formal proof.
8. Reduction adapters translate a structured PassWitness result to an external reducer's exit-code convention only at the adapter boundary.

## Backend contract

`YosysSatBackend` is the implemented backend. `EqyBackend` is an explicit interface placeholder that reports `UNSUPPORTED` until a real EQY adapter is implemented and tested. Backend responsibilities are separated into preparation, execution, proof-result interpretation, witness extraction, artifact preservation, and capability reporting.

The v0.1 semantics are defined combinational bit-vector inputs and explicit output correspondence. Width and signedness metadata come from independent elaborations. Undefined values, undriven signals, combinational loops, sequential state, memories, black boxes, and unsupported cells are not silently coerced into this contract.

## Schema and provenance

Ordinary analyses retain the Phase 1 schema. Localized analyses use the Phase 3 schema, and reductions use the Phase 4 schema. Reports preserve compatibility fields while adding flow fidelity, backend, replay, provenance, timing, and reduction audit records.

Tool provenance distinguishes the Yosys-reported version/commit, executable SHA-256, source-revision claim, whether that source was independently verified, dirty-tree information when available, patch hash, and verification method. A wrapper-supplied claim is never promoted to a verified source revision.
