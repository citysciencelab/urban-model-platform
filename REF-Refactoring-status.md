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


#### Feature III: /execution endpoint and Jobs and local Job storage
- implement remote process execution: async
- return remote job id in location header in response to POST request
- implement /jobs route (`JobList`)
- implement /jobs/job-id route
- store a local reference of a remote job


- create a (normalized) database schema for local Jobs and expand pydantic model `Job` to a SQLModel using the SQLModel library

- use a migrations system for the database schema

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
