"""
Phase 5 — byte-identical relay comparison tests.

Self-contained: imports ``compare_payloads`` from the gateway app by putting the
(hyphenated) gateway_app directory on sys.path, so it runs from the repo root
regardless of packaging. If your existing
``tests/test_phase3_byte_identical_relay.py`` has genuinely been superseded by
this file, delete that one; otherwise keep both.
"""

import os
import sys

import pytest

# Make iob-integration/gateway_app importable even though the parent dir name
# contains a hyphen (not a valid package identifier).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_GATEWAY = os.path.join(_REPO_ROOT, "iob-integration", "gateway_app")
if _GATEWAY not in sys.path:
    sys.path.insert(0, _GATEWAY)

try:
    # Prefer the proxy's own export if you wired it in (see snippet); fall back
    # to the standalone module.
    from transparent_proxy import compare_payloads  # type: ignore
except Exception:
    from payload_compare import compare_payloads  # type: ignore

from payload_compare import assert_byte_identical


def test_identical_bytes_pass():
    body = b"\x00\x01GET /telemetry HTTP/1.1\r\n\r\n{\"ok\":true}"
    result = compare_payloads(body, body)
    assert result.identical is True
    assert result.first_diff_offset == -1
    assert result.expected_len == result.actual_len == len(body)


def test_single_byte_flip_detected():
    a = b"payload-A-1234567890"
    b = b"payload-A-1234567891"  # last byte differs
    result = compare_payloads(a, b)
    assert result.identical is False
    assert result.first_diff_offset == len(a) - 1
    assert "offset" in result.reason()


def test_length_mismatch_detected():
    result = compare_payloads(b"abcdef", b"abc")
    assert result.identical is False
    assert result.expected_len == 6 and result.actual_len == 3
    assert result.first_diff_offset == 3  # diverges where the shorter ends


def test_str_is_utf8_encoded_consistently():
    # str and its utf-8 bytes must compare identical (no accidental type mismatch).
    result = compare_payloads("héllo", "héllo".encode("utf-8"))
    assert result.identical is True


def test_header_value_diff_flagged_but_body_ok():
    body = b"same-body"
    result = compare_payloads(
        body, body,
        headers_expected={"X-Trace": "abc", "Content-Type": "application/json"},
        headers_actual={"X-Trace": "XYZ", "Content-Type": "application/json"},
    )
    assert result.identical is False
    assert any("X-Trace".lower() in d for d in result.header_diffs)


def test_hop_by_hop_headers_ignored():
    body = b"same-body"
    result = compare_payloads(
        body, body,
        headers_expected={"Connection": "keep-alive", "Content-Type": "application/json"},
        headers_actual={"Connection": "close", "Content-Type": "application/json"},
    )
    # Connection is hop-by-hop; a proxy may rewrite it, so this stays identical.
    assert result.identical is True


def test_assert_helper_raises_with_reason():
    with pytest.raises(AssertionError) as exc:
        assert_byte_identical(b"aaa", b"aab")
    assert "byte-identical" in str(exc.value)
