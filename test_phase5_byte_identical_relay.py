"""
Phase 5 — Byte-Identical Relay verification tests.

This test file validates the BYTE-LEVEL relay comparison functionality
using the PayloadComparison API from payload_compare.py.

Two compare_payloads implementations exist in the codebase:
1. transparent_proxy.py - mapping-based comparison for JSON payloads
2. payload_compare.py - byte-based comparison for raw HTTP payloads

This test file validates the BYTE-BASED API (payload_compare.py).

Run:
    pytest tests/test_phase5_byte_identical_relay.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

# Make iob-integration/gateway_app importable even though the parent dir name
# contains a hyphen (not a valid package identifier).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_GATEWAY = os.path.join(_REPO_ROOT, "iob-integration", "gateway_app")
if _GATEWAY not in sys.path:
    sys.path.insert(0, _GATEWAY)

# Import the byte-based PayloadComparison API from payload_compare.py
from payload_compare import compare_payloads, assert_byte_identical, PayloadComparison


def test_identical_bytes_pass():
    """Identical byte payloads should be recognized as identical."""
    body = b"\x00\x01GET /telemetry HTTP/1.1\r\n\r\n{\"ok\":true}"
    result = compare_payloads(body, body)
    assert result.identical is True
    assert result.first_diff_offset == -1
    assert result.expected_len == result.actual_len == len(body)


def test_single_byte_flip_detected():
    """A single byte difference should be detected at the exact offset."""
    a = b"payload-A-1234567890"
    b_bytes = b"payload-A-1234567891"  # last byte differs
    result = compare_payloads(a, b_bytes)
    assert result.identical is False
    assert result.first_diff_offset == len(a) - 1
    assert "offset" in result.reason().lower()


def test_length_mismatch_detected():
    """Payloads of different lengths should be flagged."""
    result = compare_payloads(b"abcdef", b"abc")
    assert result.identical is False
    assert result.expected_len == 6 and result.actual_len == 3
    assert result.first_diff_offset == 3  # diverges where the shorter ends


def test_str_is_utf8_encoded_consistently():
    """String and its UTF-8 bytes must compare identical (no type mismatch)."""
    result = compare_payloads("héllo", "héllo".encode("utf-8"))
    assert result.identical is True


def test_header_value_diff_flagged_but_body_ok():
    """Header differences should be flagged while body remains OK."""
    body = b"same-body"
    result = compare_payloads(
        body, body,
        headers_expected={"X-Trace": "abc", "Content-Type": "application/json"},
        headers_actual={"X-Trace": "XYZ", "Content-Type": "application/json"},
    )
    assert result.identical is False
    # The X-Trace header should be in the diffs (case-insensitive)
    assert any("x-trace" in d.lower() for d in result.header_diffs)


def test_hop_by_hop_headers_ignored():
    """Hop-by-hop headers that a proxy legitimately rewrites are ignored."""
    body = b"same-body"
    result = compare_payloads(
        body, body,
        headers_expected={"Connection": "keep-alive", "Content-Type": "application/json"},
        headers_actual={"Connection": "close", "Content-Type": "application/json"},
    )
    # Connection is hop-by-hop; a proxy may rewrite it, so this stays identical.
    assert result.identical is True


def test_assert_helper_raises_with_reason():
    """assert_byte_identical should raise AssertionError with a reason."""
    with pytest.raises(AssertionError) as exc:
        assert_byte_identical(b"aaa", b"aab")
    assert "byte-identical" in str(exc.value)


def test_payload_comparison_dataclass_fields():
    """Verify PayloadComparison has all required fields."""
    result = compare_payloads(b"test", b"test2")
    assert hasattr(result, 'identical')
    assert hasattr(result, 'expected_len')
    assert hasattr(result, 'actual_len')
    assert hasattr(result, 'first_diff_offset')
    assert hasattr(result, 'expected_window')
    assert hasattr(result, 'actual_window')
    assert hasattr(result, 'header_diffs')
    assert hasattr(result, 'as_dict')
    assert hasattr(result, 'reason')


def test_empty_payloads_identical():
    """Two empty payloads should be identical."""
    result = compare_payloads(b"", b"")
    assert result.identical is True
    assert result.expected_len == result.actual_len == 0


def test_null_bytes_handled():
    """Null bytes in payloads should be handled correctly."""
    result = compare_payloads(b"\x00\x01\x02", b"\x00\x01\x02")
    assert result.identical is True


def test_binary_vs_text_difference():
    """Binary content different from text content."""
    result = compare_payloads(b"hello", b"hellx")
    assert result.identical is False
    assert result.first_diff_offset == 4


def test_missing_header_reported():
    """Missing header should be reported as a diff."""
    result = compare_payloads(
        b"body",
        b"body",
        headers_expected={"X-Custom": "value"},
        headers_actual={},
    )
    assert result.identical is False
    assert any("x-custom" in d.lower() for d in result.header_diffs)


def test_extra_header_reported():
    """Extra header should be reported as a diff."""
    result = compare_payloads(
        b"body",
        b"body",
        headers_expected={},
        headers_actual={"X-Custom": "value"},
    )
    assert result.identical is False
    assert any("x-custom" in d.lower() for d in result.header_diffs)


def test_bytearray_input_supported():
    """Bytearray inputs should be supported."""
    result = compare_payloads(bytearray(b"test"), b"test")
    assert result.identical is True


def test_memoryview_input_supported():
    """Memoryview inputs should be supported."""
    result = compare_payloads(memoryview(b"test"), b"test")
    assert result.identical is True
