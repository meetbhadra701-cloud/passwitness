from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .models import Verdict
from .minimization import minimize
from .reduction_oracle import PRESERVE_FUNCTIONAL_FAILURE, PRESERVE_LOCALIZED_FAILURE
from .runner import analyze


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="passwitness", description="Fail-closed formal correctness analysis for synthesis flows")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze", help="synthesize RTL and formally compare it with the golden design")
    analyze_parser.add_argument("--rtl", required=True, type=Path)
    analyze_parser.add_argument("--top", required=True)
    analyze_parser.add_argument("--flow", required=True, type=Path, help="Yosys script applied to a preloaded RTL design")
    analyze_parser.add_argument("--output-dir", type=Path)
    analyze_parser.add_argument("--yosys", default="yosys", help="Yosys executable or wrapper")
    analyze_parser.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    analyze_parser.add_argument("--timeout", type=float, default=300.0, help="Per-process timeout in seconds")
    analyze_parser.add_argument("--localize", action="store_true", help="capture supported synthesis checkpoints and localize the first verified divergence")
    analyze_parser.add_argument("--backend", choices=("yosys-sat", "eqy"), default="yosys-sat", help="formal backend; EQY is an explicit unsupported adapter until implemented")
    minimize_parser = subparsers.add_parser("minimize", help="reduce a formally verified synthesis failure")
    minimize_parser.add_argument("--rtl", required=True, type=Path)
    minimize_parser.add_argument("--top", required=True)
    minimize_parser.add_argument("--flow", required=True, type=Path)
    minimize_parser.add_argument("--output-dir", required=True, type=Path)
    minimize_parser.add_argument("--yosys", default="yosys")
    minimize_parser.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    minimize_parser.add_argument("--target-stage", help="required for PRESERVE_LOCALIZED_FAILURE")
    minimize_parser.add_argument(
        "--mode",
        choices=(PRESERVE_FUNCTIONAL_FAILURE, PRESERVE_LOCALIZED_FAILURE),
        default=PRESERVE_FUNCTIONAL_FAILURE,
    )
    minimize_parser.add_argument("--patched-yosys", help="optional control executable that must PASS when requested")
    minimize_parser.add_argument("--require-patched-pass", action="store_true")
    minimize_parser.add_argument("--timeout", type=float, default=120.0)
    minimize_parser.add_argument("--max-runtime", type=float, default=1800.0)
    minimize_parser.add_argument("--max-evaluations", type=int, default=100)
    minimize_parser.add_argument("--max-parallel-evaluations", type=int, default=1, help="concurrency cap; the conservative Phase 4 reducer supports only 1")
    minimize_parser.add_argument("--temp-dir", type=Path, help="directory for isolated candidate/formal work; evidence is copied back to --output-dir")
    minimize_parser.add_argument("--backend", choices=("yosys-sat", "eqy"), default="yosys-sat")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "minimize":
        result = minimize(
            rtl=args.rtl,
            top=args.top,
            flow=args.flow,
            output_dir=args.output_dir,
            yosys=args.yosys,
            target_stage=args.target_stage,
            mode=args.mode,
            patched_yosys=args.patched_yosys,
            require_patched_pass=args.require_patched_pass,
            timeout=args.timeout,
            max_runtime=args.max_runtime,
            max_evaluations=args.max_evaluations,
            max_parallel_evaluations=args.max_parallel_evaluations,
            temp_dir=args.temp_dir,
            parameters=tuple(args.param),
            backend=args.backend,
        )
        print(f"PassWitness minimization: {result.get('status', Verdict.SETUP_ERROR.value)}")
        print(f"result.json: {args.output_dir / 'result.json'}")
        print(f"report.md: {args.output_dir / 'report.md'}")
        return {
            "VERIFIED_REDUCTION": 0,
            "BUDGET_EXHAUSTED_WITH_REDUCTION": 0,
            "NO_REDUCTION_FOUND": 1,
            "SETUP_ERROR": 4,
            "UNVERIFIED_REDUCTION": 5,
        }.get(result.get("status"), 5)
    if args.command != "analyze":
        return 2
    output_dir = args.output_dir
    if output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path("passwitness-out") / stamp
    result = analyze(
        rtl=args.rtl,
        top=args.top,
        flow=args.flow,
        output_dir=output_dir,
        yosys=args.yosys,
        parameters=args.param,
        timeout=args.timeout,
        localize=args.localize,
        backend_name=args.backend,
    )
    print(f"PassWitness: {result.status.value}")
    print(f"result.json: {Path(result.output_dir) / 'result.json'}")
    print(f"report.md: {Path(result.output_dir) / 'report.md'}")
    return {Verdict.PASS: 0, Verdict.FAIL: 1, Verdict.TIMEOUT: 2, Verdict.UNSUPPORTED: 3, Verdict.SETUP_ERROR: 4, Verdict.NOT_EXECUTED: 5}[result.status]


if __name__ == "__main__":
    sys.exit(main())
