from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .models import Verdict
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
    )
    print(f"PassWitness: {result.status.value}")
    print(f"result.json: {Path(result.output_dir) / 'result.json'}")
    print(f"report.md: {Path(result.output_dir) / 'report.md'}")
    return {Verdict.PASS: 0, Verdict.FAIL: 1, Verdict.TIMEOUT: 2, Verdict.UNSUPPORTED: 3, Verdict.SETUP_ERROR: 4, Verdict.NOT_EXECUTED: 5}[result.status]


if __name__ == "__main__":
    sys.exit(main())
