# Phase 5 — wiring compare_payloads() into transparent_proxy.py
# =============================================================
#
# The transparent proxy's job is a zero-transform relay: bytes in == bytes out.
# `compare_payloads()` is the verification primitive. Two ways to satisfy the
# failing test, depending on what your test imports:
#
# CASE A — the test does `from transparent_proxy import compare_payloads`
# ----------------------------------------------------------------------
# Add this near the top of iob-integration/gateway_app/transparent_proxy.py so
# the symbol is restored at the location the test expects:
#
#     from payload_compare import compare_payloads, assert_byte_identical
#
# (payload_compare.py sits next to transparent_proxy.py in gateway_app/.)
# That single re-export "restores" the missing function without touching your
# relay logic.
#
# CASE B — the relay itself should self-verify
# --------------------------------------------
# Where the proxy finishes relaying a response, add a verification hook. Example
# shape (adapt names to your proxy):
#
#     from payload_compare import compare_payloads
#
#     def _relay_response(self, upstream_bytes: bytes, downstream_bytes: bytes,
#                         upstream_headers=None, downstream_headers=None):
#         result = compare_payloads(
#             upstream_bytes, downstream_bytes,
#             headers_expected=upstream_headers,
#             headers_actual=downstream_headers,
#         )
#         if not result.identical:
#             # log + surface; do NOT silently pass a corrupted relay
#             self.logger.error("relay integrity failure: %s", result.reason())
#         return result
#
# CASE C — the test is genuinely obsolete
# ---------------------------------------
# If, after inspecting transparent_proxy.py, `compare_payloads` was intentionally
# removed because byte-identity is now proven elsewhere (e.g.
# scripts/phase3/phase3_byte_identical_relay.py or a checksum in the relay path),
# then delete the superseded test file:
#
#     git rm tests/test_phase3_byte_identical_relay.py
#
# Only do this if the guarantee is truly covered elsewhere — otherwise prefer
# CASE A/B so the relay stays verified.
