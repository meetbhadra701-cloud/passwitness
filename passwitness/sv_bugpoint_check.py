"""sv-bugpoint interestingness-script adapter.

sv-bugpoint invokes a user script with a proposed source file and expects exit
zero only when the property remains true. This adapter translates that process
contract to the existing PassWitness ReductionOracle; it does not parse or
classify formal logs independently.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reduction_oracle import PRESERVE_FUNCTIONAL_FAILURE, PRESERVE_LOCALIZED_FAILURE, OracleConfig, ReductionOracle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PassWitness check script for sv-bugpoint")
    parser.add_argument("--top", required=True)
    parser.add_argument("--flow", required=True, type=Path)
    parser.add_argument("--yosys", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--mode", choices=(PRESERVE_FUNCTIONAL_FAILURE, PRESERVE_LOCALIZED_FAILURE), required=True)
    parser.add_argument("--target-stage")
    parser.add_argument("--patched-yosys")
    parser.add_argument("--require-patched-pass", action="store_true")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("candidate", nargs="+")
    args = parser.parse_args(argv)
    if len(args.candidate) != 1:
        return 1
    try:
        oracle = ReductionOracle(OracleConfig(
            top=args.top,
            flow=args.flow.resolve(),
            yosys=args.yosys,
            output_dir=args.output_root.resolve(),
            mode=args.mode,
            target_stage=args.target_stage,
            patched_yosys=args.patched_yosys,
            require_patched_pass=args.require_patched_pass,
            timeout=args.timeout,
        ))
        result = oracle.evaluate(Path(args.candidate[0]).resolve())
    except (OSError, ValueError):
        return 1
    return 0 if result.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
