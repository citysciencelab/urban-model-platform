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

#### Feature 0: Landing page
A simple landing page (html) which informs visitors about:
- licence
- contact
- available api routes

#### Feature I: API versioning mechanism
- OGC API processes gets a major overhaul
- backwards compatibility is probably not maintained

#### Feature II: route /processes/process-id
-> using the `Process` class for validation


#### Feature III: Jobs and local storage
- implement remote process execution: async
- implement /jobs route (`JobList`)-> fetch remote jobs
- implement job list (remote)
- store a local reference of a remote job (a job storage adapter)

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
