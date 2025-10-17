from fastapi.testclient import TestClient
from typing import Any, Dict, List, Tuple, cast

import pytest

from ump.adapters.web.fastapi import create_app
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.models.providers_config import ProviderConfig

# these test are for testing fastapi adapter routes 
# and Processmanager logic (integration tests)

class FakeProvider:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url


class FakeProvidersService(ProvidersPort):
    def __init__(self, provider: FakeProvider):
        self._provider = provider

    def load_providers(self) -> None:
        return None

    def get_providers(self) -> List[ProviderConfig]:
        return []

    def get_provider(self, provider_name: str) -> ProviderConfig:
        return ProviderConfig.model_validate({"name": self._provider.name, "url": self._provider.url})

    def get_process_config(self, provider_name: str, process_id: str):
        raise NotImplementedError

    def list_providers(self) -> List[str]:
        return [self._provider.name]

    def get_processes(self, provider_name: str) -> List[str]:
        return []

    def check_process_availability(self, provider_name: str, process_id: str) -> bool:
        return True


class FakeProcessIdValidator(ProcessIdValidatorPort):
    def validate(self, process_id_with_prefix: str) -> bool:
        return ":" in process_id_with_prefix

    def extract(self, process_id_with_prefix: str) -> Tuple[str, str]:
        if ":" in process_id_with_prefix:
            provider, pid = process_id_with_prefix.split(":", 1)
            return provider, pid
        raise ValueError("no prefix")

    def create(self, provider_prefix: str, process_id: str) -> str:
        return f"{provider_prefix}:{process_id}"


class FakeHttpClient(HttpClientPort):
    def __init__(self, post_response: Dict[str, Any]):
        # post_response is the dict the adapter should return for POST
        self._post_response = post_response

    async def __aenter__(self) -> HttpClientPort:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def get(self, url: str, timeout: float | None = None) -> Dict[str, Any]:
        raise RuntimeError("unexpected GET in this test")

    async def post(self, url: str, json: Dict[str, Any] | None = None, timeout: float | None = None, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
        # Return a provider-like response: dict with status, headers, body
        return self._post_response

    async def close(self) -> None:
        return None


def test_forward_valid_statusinfo():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # minimal statusInfo payload (fits the OGC statusInfo shape minimally)
    status_info = {"status": "accepted", "id": "remote-job-1"}

    # provider returns 201 with statusInfo body and a Location header, happy path
    provider_resp = {"status": 201, "headers": {"Location": "http://provider.local/jobs/remote-job-1"}, "body": status_info}

    http_client = FakeHttpClient(provider_resp)

    app = create_app(providers, http_client, validator)

    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )

        # TDD: expected behaviour (not yet implemented) - server should:
        # - create a local job and return 201
        # - forward the provider statusInfo as the response body
        # - set Location header pointing to the local job resource
        assert r.status_code == 201, f"expected 201, got {r.status_code}, body={r.text}"
        assert r.json() == status_info
        assert "Location" in r.headers


class MultiFakeHttpClient(HttpClientPort):
    """Fake HTTP client supporting both GET and POST mappings."""

    def __init__(self, get_responses: Dict[str, Any] | None = None, post_responses: Dict[Tuple[str, str], Any] | None = None):
        self._get = get_responses or {}
        self._post = post_responses or {}
        self.requests: List[str] = []

    async def __aenter__(self) -> HttpClientPort:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def get(self, url: str, timeout: float | None = None) -> Dict[str, Any]:
        self.requests.append(f"GET {url}")
        if url in self._get:
            return cast(Dict[str, Any], self._get[url])
        raise RuntimeError(f"no GET response for {url}")

    async def post(self, url: str, json: Dict[str, Any] | None = None, timeout: float | None = None, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
        self.requests.append(f"POST {url}")
        key = ("POST", url)
        if key in self._post:
            resp = self._post[key]
            # if resp is exception instance, raise it to simulate timeout/error
            if isinstance(resp, Exception):
                raise resp
            return cast(Dict[str, Any], resp)
        raise RuntimeError(f"no POST response for {url}")

    async def close(self) -> None:
        return None


def test_location_followup_fetches_statusinfo():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # POST returns no body but provides Location header
    post_resp = {"status": 201, "headers": {"Location": "http://provider.local/jobs/remote-job-1"}, "body": None}
    # GET on job returns valid statusInfo
    job_status = {"status": "running", "id": "remote-job-1", "type": "process"}

    http_client = MultiFakeHttpClient(get_responses={"http://provider.local/jobs/remote-job-1": job_status}, post_responses={("POST", "http://provider.local/processes/echo/execution"): post_resp})

    app = create_app(providers, http_client, validator)
    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )
        assert r.status_code == 201
        assert r.json() == job_status # client needs to validate status info, assert must
        assert "Location" in r.headers


def test_no_statusinfo_no_location_returns_failed():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # POST returns malformed body and no Location
    post_resp = {"status": 201, "headers": {}, "body": "not-a-status"}
    http_client = MultiFakeHttpClient(get_responses={}, post_responses={("POST", "http://provider.local/processes/echo/execution"): post_resp})

    app = create_app(providers, http_client, validator)
    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body.get("status") == "failed"
        assert "Location" in r.headers


def test_remote_provider_error_or_timeout():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # Simulate timeout by raising an exception from post
    http_client = MultiFakeHttpClient(post_responses={("POST", "http://provider.local/processes/echo/execution"): RuntimeError("timeout")})

    app = create_app(providers, http_client, validator)
    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )
        # TDD: server should still create a job and return 201 with failed statusInfo
        assert r.status_code == 201
        assert r.json().get("status") == "failed"
        assert "Location" in r.headers


def test_always_create_local_job():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # Provider returns immediate statusInfo
    post_resp = {"status": 200, "headers": {}, "body": {"status": "successful", "id": "remote-job-2"}}
    http_client = MultiFakeHttpClient(post_responses={("POST", "http://provider.local/processes/echo/execution"): post_resp})

    app = create_app(providers, http_client, validator)
    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )
        # even when provider returns success, server must create a local job and return 201
        assert r.status_code == 201
        assert "Location" in r.headers


def test_relative_location_header_resolution():
    provider = FakeProvider(name="infra", url="http://provider.local/")
    providers = FakeProvidersService(provider)
    validator = FakeProcessIdValidator()

    # Provider returns relative Location header
    post_resp = {"status": 202, "headers": {"Location": "/jobs/rel-1"}, "body": None}
    job_status = {"status": "running", "id": "rel-1"}
    http_client = MultiFakeHttpClient(get_responses={"http://provider.local/jobs/rel-1": job_status}, post_responses={("POST", "http://provider.local/processes/echo/execution"): post_resp})

    app = create_app(providers, http_client, validator)
    with TestClient(app) as client:
        r = client.post(
            "/processes/infra:echo/execution",
            json={"inputs": {}},
            headers={"Prefer": "respond-async"},
        )
        assert r.status_code == 201
        assert r.json() == job_status
        assert "Location" in r.headers

@pytest.mark.asyncio
async def test_execute_endpoint_forwards_201():
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
    validator = FakeProcessIdValidator()

    exec_url = "http://provider.local/processes/echo/execution"
    fake_response = {"status": 201, "headers": {"Location": "/jobs/1"}, "body": {"job": "1"}}

    http_client = MultiFakeHttpClient(post_responses={("POST", exec_url): fake_response})

    app = create_app(
        provider_config_service=cast(ProvidersPort, providers),
        http_client=cast(HttpClientPort, http_client),
        process_id_validator=cast(ProcessIdValidatorPort, validator),
        site_info=None,
    )

    with TestClient(app) as client:
        r = client.post("/processes/infra:echo/execution", json={"x":1}, headers={"Prefer": "respond-async"})
    assert r.status_code == 201
    assert r.json().get("job") == "1"