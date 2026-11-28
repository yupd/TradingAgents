"""The unauthenticated web UI is published to loopback unless explicitly opened."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"


def _web_service() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["web"]


def _published_port() -> str:
    ports = _web_service()["ports"]
    assert len(ports) == 1
    return str(ports[0])


@pytest.mark.unit
def test_published_host_defaults_to_loopback():
    assert _published_port().startswith("${STREAMLIT_BIND_ADDRESS:-127.0.0.1}:")


@pytest.mark.unit
def test_bind_address_override_point_exists():
    assert "STREAMLIT_BIND_ADDRESS" in _published_port()


@pytest.mark.unit
def test_healthcheck_targets_container_health_endpoint():
    command = " ".join(_web_service()["healthcheck"]["test"])
    assert "/_stcore/health" in command
