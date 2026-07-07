from locust import HttpUser, task, between
import random

class AIPlatformUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def test_query_endpoint(self):
        """Simulate Phase 10 integration route: /api/v1/ai/query"""
        payload = {
            "query": "What is the status of the main conveyor belt?",
            "session_id": f"perf_test_{random.randint(1000, 9999)}"
        }
        with self.client.post("/api/v1/ai/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Query failed with status {response.status_code}")

    @task(2)
    def test_predict_endpoint(self):
        """Simulate Phase 10 integration route: /api/v1/ai/predict"""
        # Sending random telemetry payloads
        payload = {
            "features": [
                {
                    "temperature": random.uniform(60.0, 100.0),
                    "vibration": random.uniform(0.01, 0.1),
                    "pressure": random.uniform(100.0, 150.0)
                }
            ]
        }
        with self.client.post("/api/v1/ai/predict", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Predict failed with status {response.status_code}")

    @task(1)
    def test_explain_endpoint(self):
        """Simulate Phase 10 integration route: /api/v1/ai/explain"""
        payload = {
            "features": {
                "temperature": 85.0,
                "vibration": 0.08,
                "pressure": 110.0
            },
            "method": "shap"
        }
        with self.client.post("/api/v1/ai/explain", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Explain failed with status {response.status_code}")
