from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_optimize_endpoint_mock():
    payload = {
        "program": "int f(int x) { int t1 = x + 0; return t1; }",
        "num_candidates": 3,
        "llm_backend": "mock",
    }
    r = client.post("/api/optimize", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["generator"] == "mock"
    assert data["summary"]["total_candidates"] == 3
    assert any(c["accepted"] for c in data["candidates"])


def test_optimize_endpoint_rejects_bad_source():
    payload = {"program": "not a valid program", "num_candidates": 1, "llm_backend": "mock"}
    r = client.post("/api/optimize", json=payload)
    assert r.status_code == 400


def test_verify_endpoint_equivalent():
    payload = {
        "original_program": "int f(int x) { return x * x; }",
        "optimized_program": "int f(int x) { return x * x; }",
    }
    r = client.post("/api/verify", json=payload)
    assert r.status_code == 200
    assert r.json()["verification"]["status"] == "EQUIVALENT"


def test_verify_endpoint_not_equivalent_has_counterexample():
    payload = {
        "original_program": "int f(int x) { return x * x; }",
        "optimized_program": "int f(int x) { return x + x; }",
    }
    r = client.post("/api/verify", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["verification"]["status"] == "NOT_EQUIVALENT"
    assert data["verification"]["counterexample"] is not None


def test_benchmarks_endpoint_lists_records():
    r = client.get("/api/benchmarks")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
