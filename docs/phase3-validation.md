# Phase 3 validation record

Validation was run on 2026-09-22 in the supplied Docker/Yosys environment. The complete test command used the clean Yosys container executable as `PASSWITNESS_YOSYS=/build/yosys`.

```text
python3 -m pytest -q tests
32 passed in 109.06s
```

The unit-only run recorded 30 passing tests. The full run included real Yosys integration for the original controls, the signed-FMA defect, three injected-fault flows, a port-correspondence failure, and relocated portable-package reproduction.

| Investigation | Overall | Localization | First transition | Flow fidelity | Replay | Formal checks |
|---|---|---|---|---|---|---:|
| Clean signed-FMA (`e8db64c...`) | FAIL | LOCALIZED | `arith_tree` | PASS | CONFIRMED | 9 |
| Patched signed-FMA (`30b851e...`) | PASS | NO_DIVERGENCE | — | PASS | not needed | 9 |
| Injected constant fault | FAIL | LOCALIZED | `injected_constant` | PASS | CONFIRMED | 3 |
| Injected wide signed coefficient | FAIL | LOCALIZED | `faulty_scale` | PASS | CONFIRMED | 3 |
| Injected final XOR substitution | FAIL | LOCALIZED | `final_fault` | PASS | CONFIRMED | 4 |

The clean signed-FMA run proved `elaborated`, `proc`, `opt`, `wreduce`, and `alumacc` equivalent, then found the first failure at `arith_tree`; later `techmap` and `abc` checkpoints also failed. Its measured synthesis time was 1.106 s, formal time 9.505 s, total localization time 15.069 s, and time to first verified divergence 8.327 s.

The clean and patched wrappers reported the same Yosys base commit (`e8db64c60`) but carried different source-revision claims. PassWitness records those as separate fields. The executable SHA-256 values were recorded, while `source_revision_verified` remained false because no independently supplied source checkout was available.

The relocation test copied the clean portable package to an unrelated temporary directory, used only the copied RTL/flow plus the external Yosys executable, and recovered `FAIL` with `arith_tree` localization. The package contained no original output-directory references; its external executable field is represented as `<external-yosys>`.

EQY was not executed: neither `eqy` nor `sby` was available in the validation environment. The Phase 3 backend interface includes an explicit unsupported EQY adapter placeholder and makes no EQY proof claim.
