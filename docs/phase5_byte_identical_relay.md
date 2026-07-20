# Phase 5 — Byte-Identical Relay Fix

## What this is

The transparent proxy must relay bytes without transformation. `compare_payloads()`
is the primitive that proves it: given the upstream payload and the downstream
payload, it confirms they are byte-for-byte identical, and on failure reports the
exact first differing offset (with a hex window) plus any relevant header diffs.

## Restore the failing symbol (most likely fix)

If `tests/test_phase3_byte_identical_relay.py` imports `compare_payloads` from
the proxy, re-export it in `iob-integration/gateway_app/transparent_proxy.py`:

```python
from payload_compare import compare_payloads, assert_byte_identical
```

`payload_compare.py` lives next to `transparent_proxy.py`, so this import works
wherever the proxy already runs.

## Behavior guarantees (verified)

- Identical bytes → `identical=True`, `first_diff_offset=-1`.
- Any single-byte difference → `identical=False` with the exact offset.
- Length differences are reported explicitly.
- `str` inputs are UTF-8 encoded so a decoded string never silently mismatches
  its own raw bytes.
- Optional header comparison is case-insensitive by name, exact by value, and
  ignores hop-by-hop headers a proxy is allowed to rewrite (Connection,
  Transfer-Encoding, Content-Length, Date, etc.).

## Removing the test instead (only if superseded)

If byte-identity is already enforced elsewhere in the relay path (a checksum, or
`scripts/phase3/phase3_byte_identical_relay.py`), and `compare_payloads` was
deliberately retired, then remove the stale test:

```bash
git rm tests/test_phase3_byte_identical_relay.py
```

Prefer restoring over deleting: a transparent relay is safer with a live
integrity check than without one.

## Run

```bash
pytest tests/test_phase5_byte_identical_relay.py -q
```
