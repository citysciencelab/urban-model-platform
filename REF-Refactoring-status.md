# Refactoring status and next steps

This document captures where the refactor to a hexagonal architecture left off and what the next steps are. Use this as a personal reference and to inform you as the coding assistant.

## High-level goal

Refactor the Urban Model Platform (UMP) codebase to follow hexagonal architecture:
- Core (business logic) depends only on ports (interfaces).
- Adapters implement ports and are injected into the core.
- Keep web adapter, persistence, and other infra concerns outside of core.

## Current state (what's implemented)

- Provider config
  - `src/ump/adapters/provider_config_file_adapter.py` implemented
    - Atomic updates, file-watcher for configmap updates, thread-safe ModelServers store.
  - `ProvidersPort` interface in `src/ump/core/interfaces/providers.py` exists and adapter implements it.

- Process ID validation
  - `ProcessIdValidatorPort` added (`src/ump/core/interfaces/process_id_validator.py`).
  - `RegexProcessIdValidator` / `ColonProcessId` adapter implemented under `src/ump/adapters/`.
  - `ProcessManager` delegates pattern validation and creation to validator adapter.

- HTTP client
  - `HttpClientPort` interface added with `__aenter__` / `__aexit__` for async context manager.
  - `AioHttpClientAdapter` implemented to map remote errors to domain exceptions.

- ProcessManager
  - `src/ump/core/managers/process_manager.py` refactored:
    - Depends on `ProvidersPort`, `HttpClientPort`, and `ProcessIdValidatorPort`.
    - Implements `fetch_processes_for_provider(provider_name)` helper.
    - Implements `get_all_processes()` which runs per-provider fetches concurrently with `asyncio.gather()`.
    - Adds an in-memory per-provider cache via `ProcessCache` helper.

- Cache
  - Small `ProcessCache` class added to `src/ump/core/managers/process_cache.py` for expiry-based in-memory caching.

- Logging
  - `LoggingPort` and `LoggingAdapter` created.
  - A `logger` instance exposed via `src/ump/core/settings.py`.

- Web adapter
  - `src/ump/adapters/web/fastapi.py` adapted to accept dependencies and create `ProcessManager` in the lifespan using an injected `http_client`.

- Main entrypoint
  - `src/ump/main.py` wires provider config adapter, process manager and FastAPI adapter and starts Uvicorn.

## Files changed (key ones)

- `src/ump/core/interfaces/providers.py` (ProvidersPort)
- `src/ump/adapters/provider_config_file_adapter.py` (Provider config file adapter)
- `src/ump/core/interfaces/process_id_validator.py` (Process ID validator port)
- `src/ump/adapters/regex_process_id_validator.py` (validator implementation)
- `src/ump/core/interfaces/http_client.py` (HttpClientPort)
- `src/ump/adapters/aiohttp_client_adapter.py` (HTTP adapter)
- `src/ump/core/managers/process_manager.py` (ProcessManager with async fetching and cache)
- `src/ump/core/managers/process_cache.py` (ProcessCache)
- `src/ump/adapters/web/fastapi.py` (web adapter wiring)
- `src/ump/core/settings.py` (logger exposure)
- `src/ump/adapters/logging_adapter.py` (logging adapter)
- `src/ump/main.py` (app entrypoint)

## Outstanding issues / TODOs

### small changes
- Improve logging usage across modules (inject `logger` where useful).
- Links in fetched processes are now optionally rewritten to local API links. This is controlled by the setting `UMP_REWRITE_REMOTE_LINKS`.
- A small utility `src/ump/core/utils/link_rewriter.py` performs the rewriting and is used by the manager.
- Fetched processes are passed through an explicit handler pipeline in `ProcessManager` (ID enforcement, link rewriting, and future handlers). This makes transformation/validation of remote process metadata explicit and extensible.

### feature extension
The following missing features must be implemented:

#### Feature 0: Landing page (completed)
A simple landing page (HTML) which informs visitors about:
- licence
- contact
- available api routes

Notes:
- Implemented as part of the web adapter using Jinja2 templates.
- Template and stylesheet are packaged with the web adapter under `src/ump/adapters/web/`:
  - `src/ump/adapters/web/templates/template.html`
  - `src/ump/adapters/web/static/style.css`
  These are mounted and served by the FastAPI adapter; the landing route also supports a JSON fallback (`?f=json` or Accept header).

#### Feature I: API versioning (implemented)

- Strategy: route-based versioning using path prefixes of the form `/v{major}.{minor}/` (for example `/v1.0/`). The landing page at `/` lists the available versions and links to each version's OpenAPI document (e.g. `/v1.0/openapi.json`) and docs (e.g. `/v1.0/docs`).
- Implementation notes:
  - Supported versions are configured via `app_settings.UMP_SUPPORTED_API_VERSIONS` (default: `["1.0"]`).
  - The web adapter (`src/ump/adapters/web/fastapi.py`) creates per-version FastAPI sub-apps and mounts them under `/v{version}` so endpoints like `/v1.0/processes` are available.
  - `src/ump/adapters/site_info_static_adapter.py` now advertises per-version routes on the landing page.
  - The landing template shows supported versions and links to their OpenAPI/docs.

This approach keeps the landing page at `/` (as required by the OGC draft) and makes breaking changes explicit by assigning them to a new version prefix.

#### Feature II: /processes/{process_id} (implemented — current state)

Status: implemented in code and wired into the web adapter. The following pieces have been completed:

- Route and web adapter
  - The FastAPI web adapter (`src/ump/adapters/web/fastapi.py`) exposes the route `/processes/{process_id}` on the parent app and on each mounted versioned sub-app (e.g. `/v1.0/processes/{process_id}`).
  - Routes declare `response_model=Process` (or `ProcessList` for list endpoints) and use `response_model_exclude_none=True` so returned JSON omits None/unset fields.

- Core manager
  - `ProcessManager.get_process(process_id: str)` was added to `src/ump/core/managers/process_manager.py` and implements the business logic to retrieve a process description.
  - Behavior:
    - If the incoming id contains a provider prefix (detected through `ProcessIdValidatorPort.extract`), the manager fetches the full process description directly from that provider's `/processes/{id}` endpoint, runs the manager's handler pipeline (ID enforcement, optional link rewriting), constructs a `Process` model and returns it.
    - If no prefix is present, the manager searches across configured providers (via `get_all_processes()` which in turn calls `fetch_processes_for_provider`) for a matching `ProcessSummary`. If found the manager attempts to fetch the detailed description; if that fetch fails the manager constructs a `Process` from the summary and returns it.
    - If not found the manager raises an `OGCProcessException` with a 404 response payload.

- Caching
  - A per-provider process-list cache (`ProcessListCache`) protects repeated list fetches.
  - A per-process cache (`ProcessCache`) caches full process descriptions by canonical id and also by the bare id (the part after the colon) to reduce repeated remote requests and accidental amplification.
  - Logging was added to record cache hits, misses and cache store events for both caches.

- Serialization & API contract
  - FastAPI `response_model` features are used for output serialization and OpenAPI generation; Pydantic models (`Process`, `ProcessSummary`, `ProcessList`) define the API contract and any None fields are excluded from responses.

Outstanding / next improvements for Feature II

- Ambiguous bare ids: current behavior picks the first matching provider when searching bare ids. Consider implementing a deterministic policy (for example: error on duplicate bare ids, prefer provider order, or require fully-qualified ids to disambiguate).
- Expose cache TTL as a configuration setting (e.g. `UMP_PROCESS_CACHE_EXPIRY_SECONDS`) so operators can tune caching behavior without code changes.

Notes:
- The implementation keeps the core free of framework code and uses the ports/adapters pattern: `ProcessManager` depends only on `ProvidersPort`, `HttpClientPort` and `ProcessIdValidatorPort` and is instantiated in the web adapter lifespan and stored on `app.state` for route handlers to use.
- Link rewriting (controlled by `UMP_REWRITE_REMOTE_LINKS`) still happens inside the manager as a handler in the processing pipeline; it will rewrite remote links into local API links when enabled.


#### Feature III: /execution endpoint and Jobs and local Job storage (STEP 1 status)

Current status (Step 1 - async execution forwarding):

- The FastAPI route `/processes/{process_id}/execution` exists in `src/ump/adapters/web/fastapi.py` and forwards requests to `app.state.process_port.execute_process(...)`.
- `ProcessManager.execute_process(...)` is implemented but currently behaves as a simple forwarder: it resolves the provider, calls the injected `HttpClientPort.post(...)`, and returns the provider's response (the adapter POST returns a dict with `status`, `headers`, `body`).
- The real HTTP adapter `AioHttpClientAdapter` is implemented in `src/ump/adapters/aiohttp_client_adapter.py`. It returns `{status, headers, body}` for POST and maps transport/JSON errors into `OGCProcessException` (502/504/etc.).

Recent TDD work and implementation notes (new insights)

- Tests added (TDD-first):
  - `tests/test_fastapi_execute_async.py` — lightweight FastAPI-focused tests describing the desired async execute semantics (always create a local job, return HTTP 201 + Location, forward statusInfo, follow provider `Location` header if needed, handle missing statusInfo as failure, map provider timeouts and transport errors, resolve relative Location headers).
  - `tests/test_aiohttp_adapter.py` — adapter unit tests covering JSON parsing, non-JSON responses, and timeout/error mappings.
  - `tests/test_fastapi_execute_e2e.py` — full-stack E2E test using the real `AioHttpClientAdapter` with `aioresponses` to mock provider flows.
  - `tests/test_process_manager.py` — unit tests for `ProcessManager` using precise fakes for ports.

- Adapter contract clarified (important for core code):
  - `HttpClientPort.post(url, json=None, timeout: float | None = None, headers: dict | None = None) -> dict`
    - Returns a dict with keys: `status` (int), `headers` (dict-like), and `body` (parsed JSON when possible, otherwise raw text).
    - Network/transport errors and JSON parse failures are mapped to `OGCProcessException` with appropriate status codes (e.g., 502, 504). Adapters must be conservative; business rules remain in core.

- JobManager proposal (new core component)
  - Introduce a `JobManager` in core to own job lifecycle concerns: job creation, remote execution forwarding, Location-following for provider-side job resources, merging/persisting `statusInfo` snapshots, and exposing job query/update operations.
  - `JobManager` depends on `HttpClientPort`, `ProvidersPort`, `ProcessIdValidatorPort`, and a `JobRepositoryPort` (persistence).
  - Keep `ProcessManager` focused on process discovery/description and delegate execute-related orchestration to `JobManager`.

- Persistence & JobRepository port
  - Add `src/ump/core/interfaces/job_repository.py` (async CRUD API) and an in-memory adapter `src/ump/adapters/job_repository_inmemory.py` for Step 1.
  - JobRepository must be swap-able with a SQLModel-backed adapter in Step 2.

- Job model & statusInfo handling
  - Add a Pydantic `Job` model in `src/ump/core/models/job.py` and a thin `StatusInfo` model mirroring OGC's `statusInfo`.
  - Important rule: DO NOT embed `inputs` or `inputs_url` inside the OGC `statusInfo` payload. The OGC `statusInfo` must remain schema-compliant. Store inputs separately on the `Job` model and expose them via a dedicated endpoint (e.g., `GET /jobs/{id}/inputs`) or a presigned/object-storage URL.
  - Minimal `Job` fields for Step 1: `id` (UUID), `process_id`, `provider`, `remote_job_id` (opt), `status` (normalized string), `status_info` (dict), `inputs` (opt, inline only for small payloads), `created/started/updated/finished` timestamps, and `links` list.

- Inputs handling & large payloads
  - For Step 1 keep tests/simple: inline small inputs and store metadata (size/checksum).
  - For production (Step 2) adopt object-storage for large inputs: keep `inputs_storage`, `inputs_url`, `inputs_checksum`, `inputs_size` on the `Job` row and do not return large blobs inside `statusInfo`.
  - Provide a presigned-upload / presigned-download flow and a secure `GET /jobs/{id}/inputs` endpoint for retrieving inputs (authorization required).

- Desired execute_process behavior (TDD summary)
  1. Validate execute request body (basic schema check) and treat `Prefer: respond-async` as async (Step 1 always async).
  2. Create a local job immediately (UUID, timestamps, provider ref, inputs metadata).
  3. Forward the execute POST to provider using `HttpClientPort.post(...)`.
  4. Inspect provider response:
     - If a valid `statusInfo` JSON body is returned, persist it as job snapshot.
     - Else if a `Location` header is present, resolve (support relative Location) and `GET` that location for `statusInfo` — persist if valid.
     - Else mark job as `failed` and record diagnostic details (provider status/text).
  5. Persist job using `JobRepository` and return HTTP 201 with `Location: /jobs/{local_job_id}` and body containing the job's `statusInfo` snapshot (even when failed).
  6. Map adapter timeouts/errors into job failure snapshots (do not crash the endpoint).

- Testing guidance (TDD -> implementation)
  - Unit tests: JobManager with InMemoryJobRepository + fake HttpClientPort for all cases (statusInfo, Location-follow, missing statusInfo, non-JSON, timeouts).
  - Adapter tests: `AioHttpClientAdapter` with `aioresponses` (JSON vs non-JSON vs timeout behavior).
  - FastAPI lightweight tests: use a fake HttpClientPort to exercise FastAPI route + JobManager logic quickly.
  - Full-stack E2E: create app wiring with real `AioHttpClientAdapter` + `aioresponses` for end-to-end verification.


Event sourcing, CQRS, and job history: design decision

- For now, we will not implement full CQRS or event sourcing. Instead, we will:
  - Implement a CRUD JobRepository with an append-only `job_statuses` (history) table (A: hybrid approach).
  - Optionally add an `append_event(job_event)` primitive to the JobRepositoryPort (B: event log for future migration/testing).
  - This gives us: fast reads, simple writes, a full audit trail, and replayability for most needs, with minimal complexity.
  - If/when we need advanced projections, replay, or scaling, we can migrate to CQRS + Event Sourcing later.

Rationale:
- CRUD + history table is simple, testable, and covers most audit/replay needs.
- CQRS + event sourcing is powerful but adds significant complexity and infra cost; only migrate if you need advanced projections, strict event audit, or heavy read/write scaling.

Immediate actionable checklist (mirrors TODO and TDD priorities):
- [ ] Add `src/ump/core/models/job.py` (Pydantic `Job` + `StatusInfo`).
- [ ] Add `src/ump/core/interfaces/job_repository.py` (async port).
- [ ] Implement `src/ump/adapters/job_repository_inmemory.py`.
- [ ] Add `src/ump/core/managers/job_manager.py` implementing `create_and_forward` and helpers to follow `Location`.
- [ ] Wire `ProcessManager.execute_process` to call `JobManager.create_and_forward` and return HTTP 201 + Location.
- [ ] Add `/jobs` + `/jobs/{id}` and `GET /jobs/{id}/inputs` routes to the web adapter (Step 1 read-only against in-memory repo).
- [ ] Add job_statuses history table and repository methods (A: hybrid approach).
- [ ] Optionally add append_event(job_event) to JobRepositoryPort and in-memory event log (B: event log for future migration/testing).
- [ ] Add tests asserting that `statusInfo` responses never include inputs or inputs_url (OGC schema compliance).

Minimal DDD guidance (commands, events, aggregates) — lightweight, incremental

To make the Job lifecycle easier to test, evolve, and (later) migrate to CQRS/Event Sourcing, introduce a small, optional DDD scaffolding that remains lightweight for Step 1:

- Concepts to add (minimal):
  - Commands: immutable intent objects used by the `JobManager` to express actions, e.g. `CreateJobCommand`, `ForwardExecutionCommand`, `FetchRemoteStatusCommand`.
  - Domain Events: immutable facts emitted when something meaningful happens, e.g. `JobCreated`, `JobForwarded`, `JobStatusUpdated`, `JobFailed`.
  - Aggregate: `JobAggregate` encapsulates in-memory domain logic and invariant checks. It receives Commands (or Events) and returns Events; it does not perform IO.
  - Event append primitive: `JobRepository.append_event(event, expected_version=None)` for persisting events to an in-memory list or events table.

- How these pieces fit together (runtime flow):
  1. API / ProcessManager creates a `CreateJobCommand` and passes it to `JobManager`.
 2. `JobManager` constructs or loads a `JobAggregate` and invokes `handle_command(cmd)` to get a list of DomainEvents.
 3. `JobManager` persists events via `JobRepository.append_event(...)` and updates the snapshot (`JobRepository.update(...)`).
 4. `JobManager` forwards the execution to the provider using `HttpClientPort`, maps provider responses to events (e.g., `JobForwarded`, `JobStatusUpdated`, `JobFailed`), persists them, and updates job snapshot.
 5. Optionally dispatch events on an in-memory bus for side-effects (projections, webhooks).

- Benefits (practical):
  - Testability: unit tests can exercise `JobAggregate` pure logic without IO.
  - Evolution: you capture discrete facts for replay/projection in the future without flipping the architecture.
  - Minimal cost: dataclasses + a few helper methods; keep Phase 1 in-memory to avoid infra overhead.

- Minimal files to add (small footprint):
  - `src/ump/core/commands.py` — small dataclasses for the command shapes.
  - `src/ump/core/events.py` — dataclasses for domain events.
  - `src/ump/core/aggregates/job_aggregate.py` — `JobAggregate` with pure `handle_command` and `apply_event` methods.
  - update `src/ump/core/interfaces/job_repository.py` to include `append_event(event, expected_version: int | None = None)`.
  - `src/ump/adapters/job_repository_inmemory.py` — implement `append_event` alongside CRUD methods.

- Tests to add (TDD):
  - `tests/unit/test_job_aggregate.py` — aggregate specs (command -> events -> state transitions).
  - `tests/unit/test_job_manager_events.py` — JobManager integration with in-memory repo and fake HttpClient.

Keep these optional: if you prefer to delay, we can add only the event-append signature on the port so tests can emit events later. Otherwise I can scaffold the lightweight DDD pieces now.
Notes:
- Keep adapters conservative: they provide raw response shape and map transport/IO errors to domain exceptions. Business logic (statusInfo merging, job lifecycle) belongs in core.
- For Step 1 use an in-memory job store; prepare SQLModel schema and migration plan for Step 2 (hybrid approach with JSONB + history table recommended).

What is NOT implemented yet for Step 1 (short):

- Local job creation/storage: there is no job model or any in-memory/persistent store yet. For Step 1 we should add a lightweight in-memory job store (replaceable by DB in Step 2).
- Execute flow: the manager must be extended to always create a local job, populate a statusInfo snapshot, follow provider `Location` headers when necessary to fetch job status, and return HTTP 201 with Location header pointing to the local job plus the statusInfo body.
- Validation: request body validation against the OGC `execute` schema is not enforced yet.

Brief notes about tests already added (TDD):

- Lightweight FastAPI integration tests: `tests/test_fastapi_execute_async.py` — TDD-style tests that cover the expected behaviors around async execute handling (forwarding valid statusInfo, following `Location`, handling missing statusInfo, provider errors/timeouts, always creating a local job, resolving relative Location headers). These tests currently express the desired behavior and will drive implementation.
- Adapter tests: `tests/test_aiohttp_adapter.py` — unit-level tests for `AioHttpClientAdapter` (JSON parsing, non-JSON -> 502, timeouts -> 504, POST text fallback).
- Full-stack E2E test: `tests/test_fastapi_execute_e2e.py` — uses the real `AioHttpClientAdapter` together with `aioresponses` to mock provider responses and verify the full call path from FastAPI -> ProcessManager -> Adapter -> provider.
- ProcessManager unit tests: `tests/test_process_manager.py` — earlier unit tests using a fake HTTP client exist to exercise manager logic in isolation.

Recommended next actions (for the next coding assistant):

1. Add a minimal `Job` model and an in-memory job store in core (e.g., `src/ump/core/models/job.py` and `src/ump/core/managers/job_store.py`). Keep the store replaceable by a DB-backed adapter later.
2. Extend `ProcessManager.execute_process` to implement the async execute flow:
  - Create a local job immediately (uuid, timestamps, provider ref, inputs).
  - Call `http_client.post(...)` to forward execution.
  - If the provider response includes a JSON body conforming to statusInfo, use it to populate the local job status snapshot.
  - Else if the provider response has a `Location` header, resolve relative locations against the provider base URL and `http_client.get(location)` to fetch the statusInfo; use it if valid.
  - Else mark the job as failed and include diagnostic details.
  - Persist the job in the in-memory store and return HTTP 201 with `Location: /jobs/{local_id}` and the job's statusInfo body.
3. Implement lightweight validation of incoming execute request bodies (Pydantic or jsonschema) and return 400 on invalid input (no job created).
4. Run the newly added TDD tests (lightweight FastAPI tests and adapter/E2E tests) and iterate until they pass. Use `aioresponses` for adapter/E2E mocks.
5. Keep the adapter conservative: it should supply raw `status/headers/body` and map transport errors to `OGCProcessException`; business rules (statusInfo merging, job lifecycle) belong to `ProcessManager`.

Pointers for the assistant taking over the task:

- FastAPI route: `src/ump/adapters/web/fastapi.py` — where `execute_process` is wired.
- Core manager: `src/ump/core/managers/process_manager.py` — extend `execute_process` to implement job creation, Location-following and statusInfo population.
- HTTP adapter: `src/ump/adapters/aiohttp_client_adapter.py` — the adapter contract (returns dict) that `ProcessManager` relies on.
- Tests to run: `tests/test_fastapi_execute_async.py`, `tests/test_fastapi_execute_e2e.py`, `tests/test_aiohttp_adapter.py`, `tests/test_process_manager.py`.

Quick prioritized checklist (for the next session):
- [ ] Create `Job` model + in-memory job store.
- [ ] Implement extended `execute_process` flow in `ProcessManager`.
- [ ] Validate execute request bodies and return 400 on invalid input.
- [ ] Update FastAPI route to return 201 + Location for async executes.
- [ ] Run adapter, lightweight, and E2E tests and make code changes until green.

```yaml
#JobControlOptions.yaml
type: string
enum:
  - sync-execute
  - async-execute
  - dismiss
```

```yaml
#statusInfo.yaml
type: object
required:
   - jobID
   - status
   - type
properties:
   processID:
      type: string
   type:
      type: string
      enum:
        - process
   jobID:
      type: string
   status:
      $ref: "statusCode.yaml"
   message:
      type: string
   created:
      type: string
      format: date-time
   started:
      type: string
      format: date-time
   finished:
      type: string
      format: date-time
   updated:
      type: string
      format: date-time
   progress:
      type: integer
      minimum: 0
      maximum: 100
   links:
      type: array
      items:
         $ref: "link.yaml"
```

```yaml
# JobList
type: object
required:
  - jobs
  - links
properties:
  jobs:
    type: array
    items:
      $ref: "statusInfo.yaml"
  links:
    type: array
    items:
      $ref: "link.yaml"
```

- deferred: remote process execution: sync

#### Feature IV: JWT-based Auth
- implement jwt based authentication
- evaluate jwt for realm roles and client roles to grant or restrict access to resources (all routes)
- add an option to grant public access to /processes route

#### Feature V: Add support for result storage
- add result storage business logic
- create an adapter for geoserver result storage (wfs, wms)
- create an adapter for ldproxy result storage (ogc api features)

Notes to assistant:
When user asks for implementation details for"ensembles":
- Ask user for reference code to gain insights what ensembles are and which mechanisms must be reimplemented
- do not reuse the user provided code, instead look for a better solution and inform the user

## Next non-immediate steps

- Add unit tests for `ProcessManager`, `ProcessCache`, and `ProviderConfigFileAdapter` (happy path + failure fallback).
- Add unit tests for the cache and manager (Task 10).

## How to run the app for local testing

1. Install dependencies (ensure `uvicorn`, `fastapi`, `aiohttp`, and `watchdog` are installed).
2. Start the app:

```bash
python -m src.ump.main
```

(Or use `uvicorn src.ump.adapters.web.fastapi:create_app --reload` after wiring DI in a runner.)

## Notes for the assistant

- The user prefers explicit dependency injection. Do not instantiate adapters inside adapters; instantiate them in `main.py` and inject.
- Keep the core free of framework code.
- When proposing changes, include small tests where feasible and run quick syntax/type checks.

---

_Last updated: 2025-10-15_
