from fastapi.testclient import TestClient


def create_ready_machine(client: TestClient) -> tuple[dict, dict]:
    machine_response = client.post(
        "/api/v1/machines",
        json={
            "name": "lab-a100-01",
            "host": "10.0.0.10",
            "port": 22,
            "username": "seed",
            "credential": {"credential_type": "password", "secret": "do-not-return"},
            "runtime_mode": "both",
        },
    )
    assert machine_response.status_code == 201
    machine = machine_response.json()
    assert machine["credential"] == "configured"
    assert "do-not-return" not in machine_response.text

    snapshot_response = client.post(f"/api/v1/machines/{machine['id']}/probe")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["fingerprint"]

    return machine, snapshot


def create_model(client: TestClient) -> dict:
    model_response = client.post(
        "/api/v1/models",
        json={
            "name": "Qwen3-32B",
            "source": "mock",
            "format": "safetensors",
            "cache_path": "/data/models/qwen3-32b",
        },
    )
    assert model_response.status_code == 201
    return model_response.json()


def test_openapi_schema_exposes_mvp_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    expected_paths = {
        "/api/v1/machines",
        "/api/v1/machines/{machine_id}/probe",
        "/api/v1/machines/{machine_id}/bootstrap",
        "/api/v1/models",
        "/api/v1/benchmarks/plan",
        "/api/v1/benchmarks/jobs",
        "/api/v1/dev/seed-demo-data",
        "/api/v1/experiments/plan",
        "/api/v1/experiments",
        "/api/v1/experiments/{experiment_id}/run-log",
        "/api/v1/experiments/{experiment_id}/reports",
        "/api/v1/reports",
        "/api/v1/plugins",
    }
    assert expected_paths.issubset(paths)


def test_demo_seed_populates_database_backed_workbench_data(client: TestClient) -> None:
    seed_response = client.post("/api/v1/dev/seed-demo-data")

    assert seed_response.status_code == 200
    seeded = seed_response.json()
    assert seeded["machines"] >= 1
    assert seeded["models"] >= 1
    assert seeded["experiments"] >= 2
    assert seeded["reports"] >= 2

    machines_response = client.get("/api/v1/machines")
    assert machines_response.status_code == 200
    assert machines_response.json()["items"][0]["name"] == "demo-a100-01"

    experiments_response = client.get("/api/v1/experiments")
    assert experiments_response.status_code == 200
    assert {experiment["runtime_mode"] for experiment in experiments_response.json()} >= {
        "container",
        "bare_metal",
    }

    reports_response = client.get("/api/v1/reports")
    assert reports_response.status_code == 200
    assert all(report["artifact_id"] for report in reports_response.json())


def test_fake_control_plane_business_loop(client: TestClient) -> None:
    machine, snapshot = create_ready_machine(client)
    assert snapshot["profile"]["hardware"]["gpu"][0]["model"] == "MockGPU"

    bootstrap_response = client.post(
        f"/api/v1/machines/{machine['id']}/bootstrap",
        json={"profile": "full", "dry_run": True},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    assert bootstrap["status"] == "succeeded"
    assert bootstrap["modules"] == ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]
    assert all("phase_results" in step for step in bootstrap["step_results"])

    model = create_model(client)
    verify_response = client.post(f"/api/v1/models/{model['id']}/verify")
    assert verify_response.status_code == 200
    assert verify_response.json() == {"verified": True}

    run_spec = {
        "machine_id": machine["id"],
        "model_id": model["id"],
        "runtime_mode": "container",
        "framework": "vllm",
        "framework_version": "0.9.0-mock",
        "framework_params": {
            "tensor_parallel_size": 4,
            "gpu_memory_utilization": 0.88,
            "max_num_seqs": 128,
        },
        "prompt_dataset": "mock_prompts_v1",
    }
    benchmark_response = client.post("/api/v1/benchmarks/jobs", json={"run_spec": run_spec})
    assert benchmark_response.status_code == 201
    benchmark = benchmark_response.json()
    assert benchmark["status"] == "succeeded"
    assert benchmark["result"]["metrics"]["tokens_per_second"] > 0

    benchmark_plan_response = client.post(
        "/api/v1/benchmarks/plan",
        json={"run_spec": run_spec, "kind": "serve", "num_prompts": 16},
    )
    assert benchmark_plan_response.status_code == 200
    benchmark_plan = benchmark_plan_response.json()
    assert "vllm bench serve" in benchmark_plan["bench_command"]
    assert "--save-result" in benchmark_plan["bench_command"]
    assert benchmark_plan["serve_command"]

    plan_response = client.post(
        "/api/v1/experiments/plan",
        json={"run_spec": run_spec, "budget": {"max_trials": 3}},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["phases"][:3] == ["Observe", "Plan", "Validate"]
    assert plan["trial_count"] == 3
    assert "vllm serve" in plan["candidates"][0]["launch_command"]

    experiment_response = client.post(
        "/api/v1/experiments",
        json={"name": "container baseline", "run_spec": run_spec, "budget": {"max_trials": 2}},
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()
    reproducibility = experiment["reproducibility"]
    assert reproducibility["machine_profile"]["host"] == "10.0.0.10"
    assert reproducibility["model_hash"] == model["sha256"]
    assert reproducibility["runtime_mode"] == "container"
    assert reproducibility["framework_params"]["tensor_parallel_size"] == 4
    assert reproducibility["prompt_dataset"] == "mock_prompts_v1"
    assert "vllm serve" in reproducibility["launch_command"]
    assert reproducibility["candidate_count"] == 2
    assert reproducibility["job_id"]

    trials_response = client.get(f"/api/v1/experiments/{experiment['id']}/trials")
    assert trials_response.status_code == 200
    trials = trials_response.json()
    assert len(trials) == 2
    assert trials[0]["result"]["logs"][0] == "trial 1 started"

    metrics_response = client.get(f"/api/v1/experiments/{experiment['id']}/metrics")
    assert metrics_response.status_code == 200
    assert len(metrics_response.json()) == 2

    run_log_response = client.get(f"/api/v1/experiments/{experiment['id']}/run-log")
    assert run_log_response.status_code == 200
    assert any("tokens_per_second" in line for line in run_log_response.json()["lines"])

    jobs_response = client.get("/api/v1/jobs")
    assert jobs_response.status_code == 200
    assert any(job["job_type"] == "experiment" for job in jobs_response.json())

    report_response = client.post(
        f"/api/v1/experiments/{experiment['id']}/reports",
        json={"template": "internal"},
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["status"] == "succeeded"
    assert "Performance Report" in report["markdown"]
    assert "do-not-return" not in report["markdown"]

    reports_response = client.get(f"/api/v1/reports?experiment_id={experiment['id']}")
    assert reports_response.status_code == 200
    assert reports_response.json()[0]["id"] == report["id"]

    artifact_response = client.get("/api/v1/artifacts")
    assert artifact_response.status_code == 200
    assert any(artifact["kind"] == "report" for artifact in artifact_response.json())
