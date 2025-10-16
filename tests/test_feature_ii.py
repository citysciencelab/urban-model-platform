import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from ump.adapters.web.fastapi import create_app

"""
Integration tests for Feature II endpoints (/processes and /processes/{id}).

These tests create the FastAPI app with injected fake provider and HTTP
client implementations. They run the app with TestClient inside a context so
the lifespan handler runs and the ProcessManager is created in
`app.state.process_port`.

Tests assert that prefixed and bare process ids are resolved to the
provider-prefixed canonical id and that the API returns the expected
structure.
"""


class FakeProvidersService:
    def __init__(self):
        self._providers = {
            "infra": SimpleNamespace(name="infra", url="http://example.org/", timeout=5, processes=[])
        }

    def list_providers(self):
        return list(self._providers.keys())

    def get_provider(self, name: str):
        return self._providers[name]


class FakeHttpClient:
    def __init__(self, responses: dict):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def get(self, url: str, timeout: float):
        # return pre-canned JSON based on url
        for k, v in self.responses.items():
            if url.startswith(k):
                return v
        return {}

    async def close(self):
        return None


class FakeProcessIdValidator:
    def validate(self, pid: str) -> bool:
        return ":" in pid

    def extract(self, pid: str):
        if ":" in pid:
            return tuple(pid.split(":", 1))
        raise ValueError("no prefix")

    def create(self, provider_prefix: str, process_id: str) -> str:
        return f"{provider_prefix}:{process_id}"


def test_get_process_by_prefixed_id():
    # prepare fake responses: provider processes and a process description
    responses = {
        "http://example.org/processes": {
            "processes": [
                {"id": "echo", "version": "1.0", "jobControlOptions": ["sync-execute"], "outputTransmission": ["value"], "links": []}
            ]
        },
        "http://example.org/processes/echo": {
            "id": "infra:echo",
            "version": "1.0",
            "jobControlOptions": ["sync-execute"],
            "outputTransmission": ["value"],
            "inputs": {},
            "outputs": {},
            "links": []
        },
    }

    providers = FakeProvidersService()
    http_client = FakeHttpClient(responses)
    validator = FakeProcessIdValidator()

    from typing import cast
    from ump.core.interfaces.providers import ProvidersPort
    from ump.core.interfaces.http_client import HttpClientPort
    from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

    app = create_app(
        provider_config_service=cast(ProvidersPort, providers),
        http_client=cast(HttpClientPort, http_client),
        process_id_validator=cast(ProcessIdValidatorPort, validator),
        site_info=None,
    )
    with TestClient(app) as client:
        resp = client.get("/processes/infra:echo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "infra:echo"


def test_get_process_by_bare_id_fallback():
    responses = {
        "http://example.org/processes": {
            "processes": [
                {"id": "infra:echo", "version": "1.0", "jobControlOptions": ["sync-execute"], "outputTransmission": ["value"], "links": []}
            ]
        },
        "http://example.org/processes/echo": {
            "id": "infra:echo",
            "version": "1.0",
            "jobControlOptions": ["sync-execute"],
            "outputTransmission": ["value"],
            "inputs": {},
            "outputs": {},
            "links": []
        },
    }

    providers = FakeProvidersService()
    http_client = FakeHttpClient(responses)
    validator = FakeProcessIdValidator()

    from typing import cast
    from ump.core.interfaces.providers import ProvidersPort
    from ump.core.interfaces.http_client import HttpClientPort
    from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

    app = create_app(
        provider_config_service=cast(ProvidersPort, providers),
        http_client=cast(HttpClientPort, http_client),
        process_id_validator=cast(ProcessIdValidatorPort, validator),
        site_info=None,
    )
    with TestClient(app) as client:
        resp = client.get("/processes/echo")
    assert resp.status_code == 200
    data = resp.json()
    # should resolve to provider-prefixed id
    assert data["id"] == "infra:echo"
