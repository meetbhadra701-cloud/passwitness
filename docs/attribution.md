# Attribution and release audit

## PassWitness code

The PassWitness source, tests, fixtures, documentation, and wrapper scripts in this repository are released under the MIT License in `LICENSE`.

## External projects

PassWitness invokes or documents these external projects; their source code is not copied into this repository:

- [Yosys](https://github.com/YosysHQ/yosys) — elaboration, synthesis, RTLIL, and SAT.
- [EQY](https://github.com/YosysHQ/eqy) — prior-art equivalence workflow; no EQY engine is bundled and the v0.1 adapter is explicit `UNSUPPORTED`.
- [SymbiYosys](https://github.com/YosysHQ/SymbiYosys) — prior-art formal orchestration; not required by v0.1.
- [Verismith](https://github.com/ymherklotz/verismith), [VlogHammer](https://github.com/YosysHQ/yosys-web/blob/master/vloghammer.in), and [VeriXmith](https://github.com/icsnju/VeriXmith) — prior-art tools, not dependencies.
- [sv-bugpoint](https://github.com/antmicro/sv-bugpoint) — optional external reducer. PassWitness contains only an adapter and shell wrapper, not sv-bugpoint source or binary.

Yosys and the other projects retain their own licenses and attribution requirements. Users supplying an executable are responsible for following its license. The repository intentionally does not bundle a Yosys installation, Docker image, compiled reducer, or copied third-party license text.

## Fixture origin

The arithmetic fixtures are small PassWitness investigation fixtures and are not presented as copied external projects. The signed-FMA fixture records the known Yosys behavior investigated by this project. It is not a Yosys source file and does not modify Yosys PR #6231.

## Audit performed for v0.1

The tracked tree was checked for private keys, common access-token formats, personal Windows/WSL paths, compiled executables, large generated directories, and private configuration. No such material was found in tracked files. The ignored `out/`, `test-output/`, caches, virtual environments, and package metadata directories are development artifacts and are excluded by `.gitignore`.
