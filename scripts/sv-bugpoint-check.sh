#!/usr/bin/env bash
set -u
args=(--top "$PW_TOP" --flow "$PW_FLOW" --yosys "$PW_YOSYS" --output-root "$PW_OUTPUT_ROOT" --mode "$PW_MODE")
if [[ -n "${PW_TARGET_STAGE:-}" ]]; then args+=(--target-stage "$PW_TARGET_STAGE"); fi
if [[ -n "${PW_PATCHED_YOSYS:-}" ]]; then args+=(--patched-yosys "$PW_PATCHED_YOSYS"); fi
if [[ -n "${PW_REQUIRE_PATCHED_PASS:-}" ]]; then args+=(--require-patched-pass); fi
args+=(--timeout "${PW_TIMEOUT:-120}")
exec python3 -m passwitness.sv_bugpoint_check "${args[@]}" "$@"
