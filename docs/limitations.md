# Limitations

PassWitness v0.1 has a deliberately small correctness contract.

## Design semantics

- Supported inputs are small combinational Verilog designs with ordinary input and output ports.
- The direct backend proves bit-vector output equivalence for defined input assignments. Width, signedness, and port correspondence are checked from independent elaborations.
- This is not a proof of timing, power, analog behavior, reset behavior, X-propagation policy, or sequential trace equivalence.
- Sequential logic, memories, clocks, inouts, arbitrary SystemVerilog constructs, unsupported Yosys cells, black boxes, undriven signals, and combinational loops are not silently supported.

## Flow coverage

- Ordinary final analysis can execute a user-selected Yosys script, subject to Yosys and PassWitness setup validation.
- Automatic checkpoint localization is supported for the version-gated `synth -top TOP -arith_tree` expansion used by the signed-FMA investigation and for explicit marked flows.
- PassWitness does not claim to localize inside an opaque macro or an arbitrary user-defined command. A flow that cannot be instrumented receives an explicit unsupported or inconclusive localization result.
- Instrumentation is checked against the ordinary final candidate. If its final behavior differs, the result is `INSTRUMENTATION_MISMATCH`, not a trusted diagnosis.

## Reduction coverage

- The built-in reducer removes complete marked blocks and is bounded by runtime and evaluation limits.
- `sv-bugpoint` is optional, external, and source-level. The adapter uses the existing PassWitness oracle; it is not a general Verilog/SystemVerilog reducer.
- C-Reduce and Yosys bugpoint are not claimed as supported interchangeable reducers in v0.1.
- Accepted candidates are independently reverified, but no reducer run claims global minimality.

## Historical evidence

The public repository contains the reduced signed-FMA reproducer, not the larger FIR4 workspace from Experiments 4–6. The checked-in `examples/fir4.v` passes under its checked-in flow and must not be described as the historical failing FIR4. Exact clean/patched signed-FMA reproduction requires the recorded compatible Yosys builds or equivalent rebuilds; external executables are not bundled.

## Provenance and portability

Executable hashes and reported tool versions are recorded. A source revision supplied by a wrapper or configuration is a claim unless the source checkout was independently inspected. Portable packages contain relative project artifacts and reproduction instructions, but still require the external Yosys dependency.
