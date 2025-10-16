import pytest
from fastapi.testclient import TestClient

from ump.adapters.web.fastapi import create_app

from typing import Dict, Any, cast
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

class FakeProvider:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.timeout = 60
        self.processes = []


class FakeProvidersService:
    def __init__(self, provider: FakeProvider):
        self._provider = provider

    def get_provider(self, provider_name: str):
        return self._provider

    def list_providers(self):
        return [self._provider.name]


class FakeValidator:
    def extract(self, process_id: str):
        if ":" in process_id:
            parts = process_id.split(":", 1)
            return parts[0], parts[1]
        raise ValueError("no prefix")


class FakeHttpClient:
    def __init__(self, responses: Dict[Any, Any]):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, timeout: float | None = None):
        return self._responses.get(url)

    async def post(self, url: str, json: Dict[str, Any] | None = None, timeout: float | None = None, headers: Dict[str, str] | None = None):
        return self._responses.get(("POST", url))

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_execute_endpoint_forwards_202():
    """
    Integration test for the execution endpoint.

    This test injects a fake HTTP client that returns a 202 Accepted
    provider response for POST /processes/{id}/execution. The FastAPI
    adapter should forward the provider response (status 202 and body)
    to the API client when Prefer: respond-async is present.

    Expected outcome: the test client receives HTTP 202 and the JSON body
    includes the job reference returned by the provider.
    """

    provider = FakeProvider("infra", "http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeValidator()

    exec_url = "http://provider.local/processes/echo/execution"
    fake_response = {"status": 202, "headers": {"Location": "/jobs/1"}, "body": {"job": "1"}}

    http_client = FakeHttpClient({("POST", exec_url): fake_response})

    app = create_app(
        provider_config_service=cast(ProvidersPort, providers),
        http_client=cast(HttpClientPort, http_client),
        process_id_validator=cast(ProcessIdValidatorPort, validator),
        site_info=None,
    )

    with TestClient(app) as client:
        r = client.post("/processes/infra:echo/execution", json={"x":1}, headers={"Prefer": "respond-async"})
    assert r.status_code == 202
    assert r.json().get("job") == "1"
