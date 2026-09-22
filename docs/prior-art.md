# Prior-art and dependency check

Checked 2026-09-21 against the project documentation and repositories below. This is a workflow comparison, not a novelty claim.

| Project | Existing capability | PassWitness Phase 1 decision |
|---|---|---|
| [Yosys](https://github.com/YosysHQ/yosys) | Verilog/SystemVerilog elaboration, synthesis passes, netlist export, and the built-in `sat` command | Reuse directly. PassWitness adds the independent golden/candidate orchestration and fail-closed artifact model around it. |
| [EQY](https://github.com/YosysHQ/eqy) | A Yosys-based equivalence-checking front-end with partitioning and configurable strategies | Do not duplicate its equivalence core. A direct Yosys miter is used in Phase 1 because the supported designs are small combinational circuits and the generated witness fields are simple. A future adapter can invoke EQY for larger flows. |
| [SymbiYosys](https://github.com/YosysHQ/sby) | `.sby` task orchestration for bounded, induction, cover, and other formal engines | Do not reimplement temporal orchestration. Phase 1 is intentionally combinational and calls Yosys directly; SBY is the planned route for sequential extensions. |
| [Verismith](https://github.com/ymherklotz/verismith) | Deterministic random valid-Verilog generation and cross-tool fuzzing | Do not become another fuzzer. PassWitness consumes an engineer-selected RTL design and flow. Verismith can provide future input corpora. |
| [VlogHammer](https://github.com/YosysHQ/yosys-web/blob/master/vloghammer.in) | Combinational Verilog regression testing across synthesis/simulation tools | Reuse the general cross-checking idea and treat VlogHammer as prior art; PassWitness focuses on one reproducible synthesis-flow investigation with explicit proof verdicts and preserved artifacts. |
| [VeriXmith](https://github.com/icsnju/VeriXmith) | Cross-checking compiler/simulator representations, canonical semantic extraction, and mutation operators | Do not reproduce its multi-tool semantic extraction or mutation system. PassWitness has a narrower, Yosys-native debugging workflow and a stricter result schema. |
| [Yosys bugpoint](https://yosyshq.readthedocs.io/projects/yosys/en/latest/using_yosys/bugpoint.html) | Reduction of a failing Yosys test case, primarily around compiler failures | Do not substitute it for the PassWitness oracle. v0.1 uses a bounded marked-block reducer and an optional `sv-bugpoint` source adapter. |
| [sv-bugpoint](https://github.com/antmicro/sv-bugpoint) | Syntax-aware SystemVerilog AST reduction driven by an executable interestingness check | Integrate only through the checked-in adapter. The external binary is not bundled; the adapter returns success only for the existing structured PassWitness oracle result. |

The release therefore contains no SAT solver, general Verilog parser, random generator, equivalence algorithm, or sequential proof engine. The generated miter uses Yosys JSON metadata for port widths and signedness, then asks Yosys SAT to prove the actual output mismatch property. The comparison above is a workflow boundary, not a scientific novelty claim.
