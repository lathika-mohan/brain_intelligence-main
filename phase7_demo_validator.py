#!/usr/bin/env python3
"""Phase 7 demo-readiness validator for the IOB Platform.

Runs the live user journey twice sequentially without restarting containers,
checks anti-stub boundaries, verifies AI graceful-degrade envelopes, and blocks
production rehearsal when mock LLM settings are active.

Usage:
    python phase7_demo_validator.py --base-url http://localhost:8000
    python phase7_demo_validator.py --base-url http://localhost:8000 --no-strict-env  # local smoke only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

try:  # optional, already pinned in requirements.txt
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

AI_UNAVAILABLE_ENVELOPE = {
    "status": "AI_UNAVAILABLE",
    "ui_message": "Advanced analytics and AI chat are temporarily offline. Local rule-based telemetry monitoring remains operational.",
}


class Phase7Failure(RuntimeError):
    """Hard-gate failure for Phase 7 exit criteria."""


@dataclass
class TimedStep:
    name: str
    started: float = field(default_factory=time.perf_counter)

    def finish(self) -> float:
        return time.perf_counter() - self.started


class Phase7DemoValidator:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        loops: int,
        strict_env: bool,
        request_timeout: float,
        short_timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.loops = loops
        self.strict_env = strict_env
        self.request_timeout = request_timeout
        self.short_timeout = short_timeout
        self.token: str | None = None
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        self.previous_risks: list[float] = []
        self.previous_shap_signatures: list[tuple[tuple[str, float, float], ...]] = []
        self.start_time = time.perf_counter()
        self.process = psutil.Process(os.getpid()) if psutil else None
        self.start_rss = self._rss_mb()

    # ------------------------------ logging ---------------------------------
    def log(self, message: str, color: str = RESET) -> None:
        elapsed = time.perf_counter() - self.start_time
        print(f"{color}[{elapsed:8.2f}s]{RESET} {message}")

    def step(self, label: str) -> TimedStep:
        self.log(f"▶ {label}", CYAN)
        return TimedStep(label)

    def pass_step(self, step: TimedStep, detail: str) -> None:
        self.log(f"✓ {step.name} ({step.finish():.3f}s) — {detail}", GREEN)

    def fail(self, message: str) -> None:
        self.log(f"✗ {message}", RED)
        raise Phase7Failure(message)

    def _rss_mb(self) -> float:
        if not self.process:
            return 0.0
        return float(self.process.memory_info().rss) / 1024 / 1024

    # ----------------------------- http utils --------------------------------
    def _client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or self.request_timeout),
            limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
            follow_redirects=True,
        )

    def _request(self, client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 500:
            self.fail(f"{method} {path} returned raw server error {response.status_code}: {response.text[:300]}")
        try:
            payload = response.json()
        except Exception as exc:
            self.fail(f"{method} {path} did not return JSON: status={response.status_code}, body={response.text[:300]}")
            raise exc
        if response.status_code >= 400:
            self.fail(f"{method} {path} returned HTTP {response.status_code}: {json.dumps(payload)[:500]}")
        return payload

    @staticmethod
    def _data(payload: Any) -> Any:
        if isinstance(payload, dict) and isinstance(payload.get("data"), (dict, list)):
            return payload["data"]
        return payload

    @staticmethod
    def _walk(obj: Any) -> Iterable[Any]:
        yield obj
        if isinstance(obj, dict):
            for value in obj.values():
                yield from Phase7DemoValidator._walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from Phase7DemoValidator._walk(value)

    @staticmethod
    def _parse_ts(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    def _assert_fresh_timestamp(self, payload: dict[str, Any], label: str, max_age_seconds: int = 180) -> None:
        timestamp_keys = {"generated_at", "last_updated", "timestamp", "detected_at", "created_at"}
        candidates: list[datetime] = []
        for obj in self._walk(payload):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in timestamp_keys:
                        parsed = self._parse_ts(value)
                        if parsed:
                            candidates.append(parsed)
        if not candidates:
            self.fail(f"{label} contains no parseable live timestamp fields")
        newest = max(candidates)
        age = abs((datetime.now(timezone.utc) - newest).total_seconds())
        if age > max_age_seconds:
            self.fail(f"{label} timestamp is stale/not live: newest={newest.isoformat()} age={age:.1f}s")

    def _extract_assets(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        if isinstance(payload, dict):
            candidates.extend([payload.get("assets"), payload.get("nominal_assets")])
            data = payload.get("data")
            if isinstance(data, dict):
                candidates.extend([data.get("assets"), data.get("nominal_assets"), data.get("asset_rows")])
            elif isinstance(data, list):
                candidates.append(data)
        for candidate in candidates:
            if isinstance(candidate, list) and candidate and all(isinstance(x, dict) for x in candidate):
                return candidate
        return []

    def _extract_risk(self, payload: dict[str, Any]) -> float:
        priority_paths = [
            ("risk_score",),
            ("data", "risk_score"),
            ("data", "failure_probability"),
            ("data", "failure_probability", "probability"),
            ("data", "failure_probability_detail", "probability"),
        ]
        for path in priority_paths:
            cur: Any = payload
            for part in path:
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    cur = None
                    break
            if isinstance(cur, (int, float)):
                return float(cur)
        for obj in self._walk(payload):
            if isinstance(obj, dict):
                value = obj.get("risk_score")
                if isinstance(value, (int, float)):
                    return float(value)
        self.fail("Predictive response has no numeric risk_score / failure_probability")
        return -1.0

    def _extract_features(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = [payload.get("features")]
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            candidates.extend([data.get("features"), data.get("local_feature_importance"), data.get("global_feature_importance")])
        for candidate in candidates:
            if isinstance(candidate, list) and candidate and all(isinstance(x, dict) for x in candidate):
                return candidate
        self.fail("XAI response does not contain a SHAP/LIME feature array")
        return []

    def _assert_no_stub_text(self, obj: Any, context: str) -> None:
        bad_terms = ("lorem", "ipsum", "placeholder", "todo", "stub", "mock-only", "hardcoded")
        for value in self._walk(obj):
            if isinstance(value, str):
                low = value.lower()
                if any(term in low for term in bad_terms):
                    self.fail(f"{context} contains stub/placeholder text: {value[:120]}")

    @staticmethod
    def _feature_signature(features: list[dict[str, Any]]) -> tuple[tuple[str, float, float], ...]:
        signature: list[tuple[str, float, float]] = []
        for row in features:
            name = str(row.get("feature_name") or row.get("name") or row.get("sensor_id") or "")
            weight = row.get("impact_weight", row.get("weight", row.get("importance", 0.0)))
            value = row.get("feature_value", row.get("value", 0.0))
            try:
                signature.append((name, round(float(weight), 6), round(float(value), 6)))
            except Exception:
                signature.append((name, 0.0, 0.0))
        return tuple(signature)

    def _assert_citations(self, payload: dict[str, Any]) -> None:
        citations = payload.get("citations")
        data = payload.get("data")
        if not citations and isinstance(data, dict):
            citations = data.get("citations")
        if not isinstance(citations, list) or not citations:
            self.fail("GraphRAG response does not include non-empty citations")
        for idx, citation in enumerate(citations, start=1):
            if not isinstance(citation, dict):
                self.fail(f"Citation #{idx} is not an object")
            node_link = citation.get("source_node_id") or citation.get("node_id") or citation.get("url") or citation.get("source_document")
            if not node_link or str(node_link).lower() in {"lorem", "placeholder", "stub"}:
                self.fail(f"Citation #{idx} has no valid node/document link: {citation}")

    # --------------------------- env validation ------------------------------
    @staticmethod
    def _read_env_file(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if not path.exists():
            return values
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            # Drop unquoted inline comments.
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip().strip('"').strip("'")
            values[key.strip()] = value
        return values

    @staticmethod
    def _read_compose_provider(path: Path) -> str | None:
        if not path.exists():
            return None
        text = path.read_text()
        match = re.search(r"LLM_PROVIDER:\s*\$\{LLM_PROVIDER:-([^}]+)\}", text)
        if match:
            return match.group(1).strip()
        match = re.search(r"LLM_PROVIDER:\s*([^\n]+)", text)
        if match:
            return match.group(1).strip().strip('"').strip("'")
        return None

    def validate_environment(self) -> None:
        step = self.step("Production environment validation")
        root = Path.cwd()
        env_values: dict[str, str] = {}
        # Later files override earlier files; OS env overrides all.
        for env_path in [root / ".env.example", root / ".env", root / ".env.production", root / ".env.local"]:
            env_values.update(self._read_env_file(env_path))
        env_values.update({k: v for k, v in os.environ.items() if k.startswith(("LLM_", "OPENAI_", "ANTHROPIC_"))})

        compose_provider = self._read_compose_provider(root / "iob-integration" / "docker-compose.yml")
        provider = (env_values.get("LLM_PROVIDER") or compose_provider or "").strip().lower()
        if provider not in {"openai", "anthropic"}:
            self.fail(f"LLM_PROVIDER must be production vendor 'openai' or 'anthropic'; observed {provider!r}")

        suspicious = []
        for key, value in env_values.items():
            if key == "LLM_PROVIDER" and value.strip().lower() == "mock":
                suspicious.append(f"{key}=mock")
            if "KEY" in key.upper() and "mock" in value.lower():
                suspicious.append(f"{key}=<mock-like>")
            if key == "LLM_MODEL_NAME" and value.lower().startswith("mock"):
                suspicious.append(f"{key}={value}")
        if suspicious:
            self.fail("Mock provider/key settings are active: " + ", ".join(suspicious))

        if self.strict_env:
            key_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
            key_value = env_values.get(key_name) or env_values.get("LLM_API_KEY") or ""
            if not key_value or key_value.startswith("changeme") or key_value.lower() in {"mock", "test", "dummy"}:
                self.fail(f"Strict env mode requires a real {key_name} (or LLM_API_KEY) in the runtime environment/.env")
        self.pass_step(step, f"LLM_PROVIDER={provider}; mock settings absent")

    # ------------------------------ journey ----------------------------------
    def authenticate(self, client: httpx.Client) -> None:
        step = self.step("Step A: Authenticate")
        payload = self._request(client, "POST", "/api/v1/auth/login", json={"username": self.username, "password": self.password})
        token = payload.get("access_token") or (payload.get("data") or {}).get("access_token")
        if not token or not isinstance(token, str):
            self.fail("Auth response missing Bearer token")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.pass_step(step, "Bearer token acquired")

    def fetch_dashboard_and_asset(self, client: httpx.Client) -> str:
        step = self.step("Step B/C: Dashboard overview + asset drilldown")
        overview = self._request(client, "GET", "/api/v1/dashboard/overview", headers=self.headers)
        assets = self._extract_assets(overview)
        if not assets:
            self.fail("Dashboard overview does not expose nominal asset arrays")
        asset = next((a for a in assets if a.get("id") == "machine07" or a.get("asset_id") == "machine07"), assets[0])
        asset_id = str(asset.get("id") or asset.get("asset_id"))
        if not asset_id:
            self.fail("Selected asset has no id/asset_id")
        asset_payload = self._request(client, "GET", f"/api/v1/assets/{asset_id}", headers=self.headers)
        self._assert_no_stub_text(asset_payload, "Asset drilldown")
        self.pass_step(step, f"{len(assets)} dashboard assets found; drilled into {asset_id}")
        return asset_id

    def run_predictive_and_xai(self, client: httpx.Client, asset_id: str, loop_index: int) -> str:
        step = self.step("Step D/E: Predictive infer + anti-stub XAI")
        features = {
            "vibration": round(3.95 + loop_index * 0.37, 4),
            "temperature": round(86.5 + loop_index * 3.2, 4),
            "pressure": round(3.1 + loop_index * 0.15, 4),
        }
        infer = self._request(
            client,
            "POST",
            "/api/v1/predictive/infer",
            headers=self.headers,
            json={"asset_id": asset_id, "features": features, "horizon_hours": 24},
        )
        if infer.get("status") == "AI_UNAVAILABLE":
            self.fail("Normal predictive loop degraded to AI_UNAVAILABLE; provider must be alive for full flight")
        self._assert_fresh_timestamp(infer, "Predictive infer")
        self._assert_no_stub_text(infer, "Predictive infer")
        risk = self._extract_risk(infer)
        if not 0.0 <= risk <= 1.0:
            self.fail(f"risk_score out of [0,1] range: {risk}")
        if abs(risk - 0.75) < 1e-9:
            self.fail("risk_score is hardcoded to forbidden stub value 0.75")
        if self.previous_risks and abs(self.previous_risks[-1] - risk) < 1e-9:
            self.fail(f"risk_score did not fluctuate between loops: {risk}")
        self.previous_risks.append(risk)

        explanation_id = str((infer.get("data") or {}).get("explanation_id") or infer.get("explanation_id") or uuid.uuid4())
        xai = self._request(client, "GET", f"/api/v1/predictive/{asset_id}/explain", headers=self.headers)
        self._assert_fresh_timestamp(xai, "XAI explain")
        self._assert_no_stub_text(xai, "XAI explain")
        features_list = self._extract_features(xai)
        for row in features_list:
            name = str(row.get("feature_name") or row.get("name") or "")
            if not name or name.lower() in {"feature", "placeholder", "stub"}:
                self.fail(f"Invalid XAI feature name: {row}")
            weight = row.get("impact_weight", row.get("importance", row.get("weight")))
            if not isinstance(weight, (int, float)):
                self.fail(f"XAI feature has no numeric impact weight: {row}")
        signature = self._feature_signature(features_list)
        if signature in self.previous_shap_signatures:
            self.fail("SHAP feature signature repeated exactly across loops; likely static stub array")
        self.previous_shap_signatures.append(signature)
        self.pass_step(step, f"risk_score={risk:.4f}; {len(features_list)} dynamic XAI features; explanation_id={explanation_id}")
        return explanation_id

    def run_graphrag(self, client: httpx.Client, asset_id: str) -> None:
        step = self.step("Step F: GraphRAG domain query + citations")
        payload = self._request(
            client,
            "POST",
            "/api/v1/graphrag/query",
            headers=self.headers,
            json={"message": f"Show detailed operational baseline parameters and maintenance history of {asset_id}", "asset_id": asset_id},
        )
        if payload.get("status") == "AI_UNAVAILABLE":
            self.fail("Normal GraphRAG loop degraded to AI_UNAVAILABLE; production LLM must be reachable")
        self._assert_fresh_timestamp(payload, "GraphRAG query")
        self._assert_no_stub_text(payload, "GraphRAG query")
        self._assert_citations(payload)
        self.pass_step(step, "citation node/document links validated")

    def run_alert_state_machine(self, client: httpx.Client, asset_id: str) -> None:
        step = self.step("Step G: Reactive alert inject + resolve")
        injected = self._request(
            client,
            "POST",
            "/api/v1/test/inject-alarm",
            headers=self.headers,
            json={"asset_id": asset_id, "metric": "bearing_temperature", "value": 145.2},
        )
        alert = injected.get("data") if isinstance(injected.get("data"), dict) else injected
        alert_id = str(alert.get("alert_id") or alert.get("id") or "") if isinstance(alert, dict) else ""
        if not alert_id:
            self.fail("Alert injection response missing alert id")
        resolved = self._request(
            client,
            "POST",
            "/api/v1/alerts/resolve",
            headers=self.headers,
            json={"alert_id": alert_id, "asset_id": asset_id},
        )
        if resolved.get("resolved_count", 0) < 1 and not resolved.get("resolved_alerts"):
            self.fail(f"Alert resolve did not close injected alert {alert_id}: {resolved}")
        active = self._request(client, "GET", "/api/v1/alerts/active", headers=self.headers)
        active_rows = active.get("alerts") or active.get("data") or []
        if any(isinstance(a, dict) and a.get("asset_id") == asset_id and a.get("status") == "ACTIVE" for a in active_rows):
            self.fail(f"Injected alert {alert_id} is still ACTIVE after resolve")
        self.pass_step(step, f"alert_id={alert_id} closed cleanly")

    def run_degrade_check(self) -> None:
        step = self.step("Graceful-degrade check: ai-platform unavailable frontend envelope")
        headers = dict(self.headers)
        headers["X-Force-AI-Unavailable"] = "true"
        with self._client(timeout=self.short_timeout) as client:
            checks = [
                ("POST", "/api/v1/predictive/infer", {"asset_id": "machine07", "features": {"vibration": 8.0, "temperature": 120.0}}),
                ("POST", "/api/v1/chat", {"prompt": "What should I inspect first?", "history": []}),
            ]
            for method, path, body in checks:
                try:
                    response = client.request(method, path, headers=headers, json=body)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
                    self.fail(f"{path} leaked a raw network exception instead of UI envelope: {exc}")
                if response.status_code >= 500:
                    self.fail(f"{path} returned raw HTTP {response.status_code} instead of AI_UNAVAILABLE envelope")
                try:
                    payload = response.json()
                except Exception:
                    self.fail(f"{path} returned non-JSON degrade payload: {response.text[:300]}")
                status_value = payload.get("status") or (payload.get("data") or {}).get("status")
                message_value = payload.get("ui_message") or (payload.get("data") or {}).get("ui_message")
                if status_value != AI_UNAVAILABLE_ENVELOPE["status"] or message_value != AI_UNAVAILABLE_ENVELOPE["ui_message"]:
                    self.fail(f"{path} did not return required AI_UNAVAILABLE envelope: {payload}")
        self.pass_step(step, "predictive and chat endpoints return structured UI fallback envelope")

    def run_all(self) -> None:
        self.log(f"{BOLD}🚀 Phase 7 Demo Validator starting against {self.base_url}{RESET}", BLUE)
        if self.strict_env:
            self.validate_environment()
        else:
            self.log("⚠ Environment validation skipped (--no-strict-env); this is not a production sign-off run.", YELLOW)

        with self._client() as client:
            self.authenticate(client)
            for loop_index in range(1, self.loops + 1):
                self.log(f"{BOLD}— Full journey loop {loop_index}/{self.loops} —{RESET}", BLUE)
                loop_step = TimedStep(f"Full journey loop {loop_index}")
                asset_id = self.fetch_dashboard_and_asset(client)
                self.run_predictive_and_xai(client, asset_id, loop_index)
                self.run_graphrag(client, asset_id)
                self.run_alert_state_machine(client, asset_id)
                self.pass_step(loop_step, f"loop {loop_index} completed without container restart")

        self.run_degrade_check()
        end_rss = self._rss_mb()
        if self.process and end_rss - self.start_rss > 100:
            self.fail(f"Validator RSS grew by {end_rss - self.start_rss:.1f} MB; investigate socket/memory leakage")
        total = time.perf_counter() - self.start_time
        self.log(f"🎉 PHASE 7 HARD GATE PASSED in {total:.2f}s; RSS delta={end_rss - self.start_rss:.1f} MB", GREEN)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 7 demo-readiness hard-gate checks.")
    parser.add_argument("--base-url", default=os.getenv("IOB_GATEWAY_URL", "http://localhost:8000"), help="Gateway base URL")
    parser.add_argument("--username", default=os.getenv("IOB_DEMO_USERNAME", "demo_operator"))
    parser.add_argument("--password", default=os.getenv("IOB_DEMO_PASSWORD", "secure_password_2026"))
    parser.add_argument("--loops", type=int, default=2, help="Full journey loops to execute sequentially")
    parser.add_argument("--timeout", type=float, default=10.0, help="Normal request timeout seconds")
    parser.add_argument("--short-timeout", type=float, default=1.0, help="Forced short timeout for degrade probes")
    parser.add_argument("--no-strict-env", action="store_true", help="Skip production LLM/key validation (local smoke only)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.loops < 2:
        print(f"{YELLOW}Phase 7 requires two sequential loops; overriding --loops to 2.{RESET}")
        args.loops = 2
    validator = Phase7DemoValidator(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        loops=args.loops,
        strict_env=not args.no_strict_env,
        request_timeout=args.timeout,
        short_timeout=args.short_timeout,
    )
    try:
        validator.run_all()
    except Phase7Failure as exc:
        print(f"\n{RED}{BOLD}PHASE 7 HARD GATE FAILED:{RESET} {exc}")
        return 1
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted by operator.{RESET}")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
