from __future__ import annotations

import re

from .models import Verdict


SUCCESS_MARKER = re.compile(r"SAT proof finished\s*-\s*no model found:\s*SUCCESS!", re.I)
FAIL_MARKER = re.compile(r"SAT proof finished\s*-\s*model found:\s*FAIL!", re.I)
TIMEOUT_MARKER = re.compile(r"\b(?:timeout|timed out|time limit)\b", re.I)
ERROR_MARKER = re.compile(r"(?:^|\n)\s*(?:ERROR|FATAL):", re.I)


def classify_formal_log(
    log: str,
    returncode: int | None = None,
    *,
    timed_out: bool = False,
) -> tuple[Verdict, str]:
    """Classify a Yosys SAT log using proof markers, never exit status alone."""

    if timed_out:
        return Verdict.TIMEOUT, "The formal process exceeded its configured timeout."
    if FAIL_MARKER.search(log):
        return Verdict.FAIL, "The SAT solver found a model that violates output equivalence."
    if SUCCESS_MARKER.search(log) and not ERROR_MARKER.search(log):
        return Verdict.PASS, "The SAT solver established the equivalence property."
    if TIMEOUT_MARKER.search(log):
        return Verdict.TIMEOUT, "The formal log reports a timeout without a completed proof."
    if ERROR_MARKER.search(log) or (returncode not in (None, 0)):
        return Verdict.SETUP_ERROR, "The formal check did not complete with a trustworthy proof result."
    return Verdict.SETUP_ERROR, "No recognized formal proof verdict was present in the log."
