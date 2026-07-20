"""
Phase 5 — Byte-Identical Relay verification.

``compare_payloads()`` is the primitive the transparent proxy uses to prove that
what it relayed downstream is byte-for-byte identical to what it received
upstream (a "transparent"/zero-transform relay). It is intentionally
dependency-free so it can run in the gateway container and in CI without extra
packages.

Public API
----------
compare_payloads(expected, actual, *, headers_expected=None, headers_actual=None)
        -> PayloadComparison
assert_byte_identical(expected, actual, **kw) -> None   (raises AssertionError)

Design notes
------------
* "Byte-identical" means exactly that: no normalization, no whitespace/JSON
  re-encoding, no header reordering by default. Any transform breaks the guarantee.
* Inputs may be ``bytes``, ``bytearray``, ``memoryview`` or ``str``. ``str`` is
  encoded as UTF-8 before comparison so callers don't silently compare a decoded
  string against raw bytes. Pass bytes when you truly want raw-wire semantics.
* The result carries the first differing offset and a small hex window around it,
  which is what you want in a relay failure report instead of a giant blob dump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

Payload = Union[bytes, bytearray, memoryview, str]


def _to_bytes(value: Payload) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    raise TypeError(
        f"compare_payloads expected bytes/str, got {type(value).__name__}"
    )


def _first_diff_offset(a: bytes, b: bytes) -> int:
    """Return the index of the first differing byte, or -1 if one is a prefix."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return -1  # equal up to the shorter length (length diff handled by caller)


def _hex_window(data: bytes, offset: int, radius: int = 8) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + radius + 1)
    return data[start:end].hex(" ")


@dataclass
class PayloadComparison:
    """Structured result of a byte-identical comparison."""

    identical: bool
    expected_len: int
    actual_len: int
    first_diff_offset: int = -1               # -1 when bodies match
    expected_window: Optional[str] = None     # hex around first diff
    actual_window: Optional[str] = None
    header_diffs: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "identical": self.identical,
            "expected_len": self.expected_len,
            "actual_len": self.actual_len,
            "first_diff_offset": self.first_diff_offset,
            "expected_window": self.expected_window,
            "actual_window": self.actual_window,
            "header_diffs": self.header_diffs,
        }

    def reason(self) -> str:
        if self.identical:
            return "byte-identical"
        parts: List[str] = []
        if self.expected_len != self.actual_len:
            parts.append(
                f"length differs (expected {self.expected_len}, got {self.actual_len})"
            )
        if self.first_diff_offset >= 0:
            parts.append(
                f"first byte diff at offset {self.first_diff_offset}: "
                f"expected [{self.expected_window}] got [{self.actual_window}]"
            )
        if self.header_diffs:
            parts.append("header diffs: " + "; ".join(self.header_diffs))
        return "; ".join(parts) or "not identical"


def _compare_headers(
    expected: Optional[Dict[str, str]],
    actual: Optional[Dict[str, str]],
) -> List[str]:
    """Compare relayed headers case-insensitively by name, exactly by value.

    Hop-by-hop headers that a proxy legitimately rewrites are ignored so they
    don't register as false relay failures.
    """
    if expected is None and actual is None:
        return []
    expected = expected or {}
    actual = actual or {}

    ignore = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
        "date", "server", "via",
    }

    def norm(d: Dict[str, str]) -> Dict[str, str]:
        return {k.lower(): v for k, v in d.items() if k.lower() not in ignore}

    e, a = norm(expected), norm(actual)
    diffs: List[str] = []
    for key in sorted(set(e) | set(a)):
        if key not in a:
            diffs.append(f"missing header '{key}'")
        elif key not in e:
            diffs.append(f"unexpected header '{key}'")
        elif e[key] != a[key]:
            diffs.append(f"header '{key}' value differs")
    return diffs


def compare_payloads(
    expected: Payload,
    actual: Payload,
    *,
    headers_expected: Optional[Dict[str, str]] = None,
    headers_actual: Optional[Dict[str, str]] = None,
) -> PayloadComparison:
    """
    Compare two relay payloads for byte-for-byte equality.

    Returns a :class:`PayloadComparison`. ``identical`` is True only when the
    bodies match exactly and (when headers are supplied) no relevant header
    differs. Body comparison is done first because that is the core relay
    guarantee.
    """
    e = _to_bytes(expected)
    a = _to_bytes(actual)

    header_diffs = _compare_headers(headers_expected, headers_actual)

    if e == a:
        return PayloadComparison(
            identical=not header_diffs,
            expected_len=len(e),
            actual_len=len(a),
            header_diffs=header_diffs,
        )

    offset = _first_diff_offset(e, a)
    if offset == -1:
        # One body is a strict prefix of the other -> diverge at the shorter len.
        offset = min(len(e), len(a))

    return PayloadComparison(
        identical=False,
        expected_len=len(e),
        actual_len=len(a),
        first_diff_offset=offset,
        expected_window=_hex_window(e, offset),
        actual_window=_hex_window(a, offset),
        header_diffs=header_diffs,
    )


def assert_byte_identical(
    expected: Payload,
    actual: Payload,
    *,
    headers_expected: Optional[Dict[str, str]] = None,
    headers_actual: Optional[Dict[str, str]] = None,
) -> None:
    """Raise ``AssertionError`` (with a precise reason) if not byte-identical."""
    result = compare_payloads(
        expected, actual,
        headers_expected=headers_expected,
        headers_actual=headers_actual,
    )
    if not result.identical:
        raise AssertionError(f"relay not byte-identical: {result.reason()}")
