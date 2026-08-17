from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

ROOT = Path(__file__).parents[2]
JSON_OBJECT = TypeAdapter(dict[str, Any])
EXPECTED_IMAGES = {
    "kafka": "apache/kafka:4.3.1",
    "mongodb": "mongo:7.0.37-jammy",
    "postgres": "pgvector/pgvector:0.8.5-pg17-bookworm",
    "redis": "redis:7.2.14-alpine",
}


def render_compose_config() -> dict[str, Any]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "--profile",
            "core",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return JSON_OBJECT.validate_python(json.loads(result.stdout))


def test_core_dependencies_use_pinned_images_and_healthchecks() -> None:
    services = render_compose_config()["services"]

    assert {name: services[name]["image"] for name in EXPECTED_IMAGES} == EXPECTED_IMAGES
    assert all(services[name]["healthcheck"]["test"] for name in EXPECTED_IMAGES)


def test_published_dependency_ports_only_bind_to_loopback() -> None:
    services = render_compose_config()["services"]

    published_ports = [port for name in EXPECTED_IMAGES for port in services[name].get("ports", [])]
    assert len(published_ports) == 4
    assert all(port["host_ip"] == "127.0.0.1" for port in published_ports)


def test_stateful_dependencies_use_named_volumes() -> None:
    config = render_compose_config()

    assert {"kafka_data", "mongodb_data", "postgres_data", "redis_data"} <= set(config["volumes"])
    assert all(config["services"][name].get("volumes") for name in EXPECTED_IMAGES)


def test_kafka_bootstrap_prepares_the_named_volume_without_deleting_data() -> None:
    services = render_compose_config()["services"]

    assert (
        services["kafka"]["depends_on"]["kafka-init"]["condition"]
        == "service_completed_successfully"
    )
    assert services["kafka-init"]["user"] == "0:0"
    assert any("chown -R 1000:1000" in argument for argument in services["kafka-init"]["command"])


def test_airflow_profile_contains_scheduler_and_api_server() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "--profile",
            "airflow",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    services = JSON_OBJECT.validate_python(json.loads(result.stdout))["services"]
    assert {"airflow-init", "airflow-scheduler", "airflow-api-server"} <= set(services)
    assert services["ai-content"]["build"]["dockerfile"] == "services/runtime.Dockerfile"
    assert services["airflow-api-server"]["ports"][0]["host_ip"] == "127.0.0.1"


def test_ai_content_has_production_provider_defaults_and_internal_database_urls() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "--profile",
            "core",
            "--profile",
            "app",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    services = JSON_OBJECT.validate_python(json.loads(result.stdout))["services"]
    ai_environment = services["ai-content"]["environment"]
    assert ai_environment["FOOTBALLPULSE_ENV"] == "production"
    assert ai_environment["FOOTBALLPULSE_AI_PROVIDER"] == "kaggle"
    assert ai_environment["FOOTBALLPULSE_AI_ALLOW_MOCK"] == "false"
    assert ai_environment["FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE"] == "false"
    assert ai_environment["FOOTBALLPULSE_MONGODB_URL"].startswith("mongodb://mongodb:27017/")
