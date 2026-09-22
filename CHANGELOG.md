# Changelog

## 0.1.0 — release preparation

PassWitness v0.1 packages the Phase 1–4.1 workflow:

- fail-closed Yosys SAT equivalence checking for supported combinational Verilog;
- version-aware and marked-flow RTLIL checkpoints;
- verified synthesis-stage localization and fixed-witness replay;
- executable hashing and explicit source-revision provenance fields;
- bounded marked-block reduction with candidate hashing, audit counters, and independent re-verification;
- an optional `sv-bugpoint` interestingness adapter;
- portable evidence packages with relative artifact references;
- unit, negative-control, and Yosys-backed integration tests.

The release evidence includes a signed-FMA reduction from 325 to 305 bytes and an intentionally injected-fault reduction from 1110 to 326 bytes. Neither result claims global minimality. The larger FIR4 workspace used in the original experiments was not available during Phase 4.1 and is not part of this release claim.
