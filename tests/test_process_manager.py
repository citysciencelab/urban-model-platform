import pytest

from typing import Any, Dict, cast

from ump.core.managers.process_manager import ProcessManager
from ump.core.models.process import Process
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

"""
Unit tests for ProcessManager.

These tests exercise the core manager logic by injecting a fake HTTP client
and a fake provider configuration service. They assert both happy-path
behaviour (fetching and parsing a remote process description) and execution
forwarding semantics (honouring the `Prefer: respond-async` header and
returning the provider's 202 Accepted response).

The tests use small fakes rather than network mocks to keep them fast and
deterministic.
"""


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
    
    def create(self, provider_prefix: str, process_id: str) -> str:
        return f"{provider_prefix}:{process_id}"


class FakeHttpClient:
    # allow arbitrary keys (str or tuple) to map responses
    def __init__(self, responses: Dict[object, Any]):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, timeout: float | None = None):
        # Return the configured response or raise
        return self._responses.get(url)

    async def post(self, url: str, json: Dict[str, Any] | None = None, timeout: float | None = None, headers: Dict[str, str] | None = None):
        return self._responses.get(("POST", url))

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_get_process_from_provider_happy_path():
    # Happy path: the ProcessManager should fetch a process description
    # from the configured provider and return a validated Process model.
    # Expected outcome: a Process with id 'infra:echo' is returned.
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeValidator()

    proc_url = "http://provider.local/processes/echo"
    fake_proc = {
        "id": "infra:echo",
        "version": "1.0",
        "jobControlOptions": ["sync-execute"],
        "outputTransmission": ["value"],
        "inputs": {},
        "outputs": {},
        "links": [],
    }

    http_client = FakeHttpClient({proc_url: fake_proc})

    async with http_client as client:
        manager = ProcessManager(
            cast(ProvidersPort, providers),
            cast(HttpClientPort, client),
            process_id_validator=cast(ProcessIdValidatorPort, validator),
        )
        model: Process = await manager.get_process("infra:echo")
        assert model.id == "infra:echo"
        assert getattr(model, "title", None) == "Echo Process"


@pytest.mark.asyncio
async def test_execute_process_forwards_and_honors_prefer_header():
    # Execution forwarding: when the caller sends Prefer: respond-async and
    # the remote provider returns 202 Accepted, the manager should forward
    # the provider response as-is (for now). Expected outcome: a dict
    # containing status == 202 is returned from execute_process.
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeValidator()

    exec_url = "http://provider.local/processes/echo/execution"
    fake_response = {"status": 202, "headers": {"Location": "/jobs/1"}, "body": {"job": "1"}}

    http_client = FakeHttpClient({("POST", exec_url): fake_response})

    async with http_client as client:
        manager = ProcessManager(
            cast(ProvidersPort, providers),
            cast(HttpClientPort, client),
            process_id_validator=cast(ProcessIdValidatorPort, validator),
        )
        resp = await manager.execute_process("infra:echo", body={"x": 1}, headers={"Prefer": "respond-async"})
        assert isinstance(resp, dict)
        assert resp.get("status") == 202
