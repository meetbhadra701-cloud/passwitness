import json

from passwitness.formal import load_ports, parse_model, port_correspondence_errors, write_miter
from passwitness.models import Port


def test_miter_keeps_port_widths_and_signedness(tmp_path):
    ports = [Port("a", "input", 4, True), Port("y", "output", 8, True), Port("z", "output", 1, False)]
    path = tmp_path / "miter.v"
    write_miter(path, "gold", ports, {"W": "4"})
    text = path.read_text()
    assert "input signed [3:0] a" in text
    assert "output signed [7:0] reference_y" in text
    assert ".W(4)" in text
    assert "(reference_y ^ candidate_y)" in text
    assert "(reference_z ^ candidate_z)" in text


def test_load_ports_reads_yosys_metadata(tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"modules": {"top": {"ports": {
        "a": {"direction": "input", "signed": 1, "bits": [1, 2]},
        "y": {"direction": "output", "bits": [3]},
    }, "cells": {}}}}))
    ports = load_ports(path, "top")
    assert [(port.name, port.width, port.signed) for port in ports] == [("a", 2, True), ("y", 1, False)]


def test_parse_model_preserves_decimal_hex_and_binary():
    model = parse_model("  \\a                          7         7            0111\n")
    assert model["a"] == {"decimal": 7, "hex": "7", "binary": "0111"}


def test_port_correspondence_is_explicit():
    expected = [Port("a", "input", 4, True), Port("y", "output", 8, False)]
    actual = [Port("a", "input", 3, True), Port("z", "output", 8, False)]
    errors = port_correspondence_errors(expected, actual)
    assert "candidate is missing port 'y'" in errors
    assert "candidate has unexpected port 'z'" in errors
    assert "port 'a' width differs: 4 != 3" in errors
