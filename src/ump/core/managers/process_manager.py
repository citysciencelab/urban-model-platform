# ump/core/managers/process_manager.py
from __future__ import annotations
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from ump.core.exceptions import OGCProcessException
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.managers.process_cache import ProcessCache, ProcessListCache
from ump.core.managers.job_manager import JobManager
from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.models.link import Link
from ump.core.models.ogcp_exception import OGCExceptionResponse
from ump.core.models.process import Process, ProcessList, ProcessSummary
from ump.core.models.providers_config import ProviderConfig
from ump.core.settings import app_settings, logger
from ump.core.utils.link_rewriter import rewrite_links_to_local


class ProcessManager(ProcessesPort):
    def __init__(
        self,
        provider_config_service: ProvidersPort,
        http_client: HttpClientPort,
        process_id_validator: ProcessIdValidatorPort,
        job_repository: JobRepositoryPort | None = None,
        cache_expiry_seconds: int = 300,
    ) -> None:
        self.provider_config_service = provider_config_service
        self.http_client = http_client
        self.process_id_validator = process_id_validator
        self.job_repository = job_repository
        self._process_cache = ProcessListCache[ProcessSummary](
            expiry_seconds=cache_expiry_seconds
        )
        # cache individual process descriptions by id
        self._process_cache_by_id = ProcessCache[Process](
            expiry_seconds=cache_expiry_seconds
        )
        # Will be set by composition root after instantiation.
        self.job_manager: Optional[JobManager] = None

    # A pipeline of handlers (functions) that transform a fetched process dict.
        # Each handler has signature: handler(provider_name: str, proc: Dict[str, Any]) -> Dict[str, Any]
        # Handlers can raise ValueError to indicate the process should be skipped.
        self._process_handlers: List[
            Callable[[str, Dict[str, Any]], Dict[str, Any]]
        ] = [
            self._handle_process_id,
            # Fill in spec-required defaults if upstream omits optional-but-expected
            # sections we rely on (lenient mode). This must run early so later
            # handlers can assume presence.
            self._handle_fill_defaults,
            # Remove / ignore malformed metadata entries so validation doesn't fail.
            self._handle_sanitize_metadata,
            self._handle_rewrite_links,
        ]

    def add_process_handler(
        self, handler: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    ):
        """Register an additional process handler at runtime."""
        self._process_handlers.append(handler)

    # --- Default handlers -------------------------------------------------
    def _handle_process_id(
        self, provider_name: str, proc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enforce and create the canonical process id using the injected validator.

        Raises ValueError if the id cannot be created/validated.
        """
        raw_proc_id = proc.get("id")
        if raw_proc_id is None:
            raise ValueError("missing process id")
        full_proc_id = self.process_id_validator.create(provider_name, raw_proc_id)
        proc["id"] = full_proc_id
        return proc

    def _handle_rewrite_links(
        self, provider_name: str, proc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rewrite remote links to local links if enabled in settings.
        This handler is a no-op if links are missing or rewriting is disabled.
        """

        if not app_settings.UMP_REWRITE_REMOTE_LINKS:
            return proc

        if "links" not in proc or not isinstance(proc.get("links"), list):
            return proc
        try:
            from ump.core.models.link import Link
            from ump.core.utils.link_rewriter import rewrite_links_to_local

            proc_links = [Link(**l) for l in proc.get("links", [])]
            proc["links"] = [
                l.model_dump()
                for l in rewrite_links_to_local(str(proc.get("id")), proc_links)
            ]
        except Exception:
            logger.warning(f"Failed to rewrite links for process {proc.get('id')}")
            # leave them empty
            proc["links"] = []

        return proc

    def _handle_fill_defaults(
        self, provider_name: str, proc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Leniently accept partially non-spec processes by synthesizing
        reasonable defaults. We NEVER drop a process solely because fields like
        links, version or jobControlOptions are missing – upstream catalogs are
        often sparse.

        Rules:
        - version: default to "0.0.0" if missing
        - jobControlOptions: default to ["sync-execute", "async-execute"] (common superset)
        - outputTransmission: default to ["value"]
        - links: if missing/empty insert a minimal 'self' placeholder; will later be
          rewritten if link rewriting enabled. We insert the canonical id after
          the id handler has run (hence this handler is placed after _handle_process_id).
        - keywords: ensure list type
        - metadata: ensure list type
        """
        # version
        proc.setdefault("version", "0.0.0")

        # jobControlOptions
        jco = proc.get("jobControlOptions")
        if not isinstance(jco, list) or not jco:
            proc["jobControlOptions"] = ["sync-execute", "async-execute"]

        # outputTransmission
        ot = proc.get("outputTransmission")
        if not isinstance(ot, list) or not ot:
            proc["outputTransmission"] = ["value"]

        # links
        links = proc.get("links")
        if not isinstance(links, list) or not links:
            # minimal placeholder; may be rewritten later; rel 'self' conventional
            proc["links"] = [
                {
                    "href": f"/processes/{proc.get('id', '')}",
                    "rel": "self",
                    "type": "application/json",
                    "title": proc.get("title") or proc.get("id", "process"),
                }
            ]

        # keywords / metadata normalization to lists
        if "keywords" in proc and not isinstance(proc["keywords"], list):
            proc["keywords"] = [proc["keywords"]]
        if "metadata" in proc and not isinstance(proc["metadata"], list):
            proc["metadata"] = [proc["metadata"]]

        return proc

    def _handle_sanitize_metadata(
        self, provider_name: str, proc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Drop malformed metadata entries (missing required keys) instead of failing.

        Upstream catalogs sometimes place arbitrary provenance dicts into `metadata`.
        Our `Metadata` model expects: title, role, href. If an entry lacks any of
        these keys we silently drop it and log once per process (debug level) with
        a count of removed entries. If after filtering nothing remains we remove
        the metadata key entirely so Pydantic treats it as absent.

        We apply the same logic to output metadata (each item in `outputs`).
        """
        removed_count = 0
        # Process-level metadata
        if isinstance(proc.get("metadata"), list):
            valid_meta: List[Dict[str, Any]] = []
            for m in proc["metadata"]:
                if not isinstance(m, dict):
                    removed_count += 1
                    continue
                if not all(k in m for k in ("title", "role", "href")):
                    removed_count += 1
                    continue
                valid_meta.append(m)
            if valid_meta:
                proc["metadata"] = valid_meta
            else:
                proc.pop("metadata", None)
        # Outputs metadata (if detailed description already fetched)
        if isinstance(proc.get("outputs"), dict):
            for out_id, out_def in list(proc["outputs"].items()):
                meta_list = out_def.get("metadata")
                if isinstance(meta_list, list):
                    valid_out_meta: List[Dict[str, Any]] = []
                    for m in meta_list:
                        if not isinstance(m, dict):
                            removed_count += 1
                            continue
                        if not all(k in m for k in ("title", "role", "href")):
                            removed_count += 1
                            continue
                        valid_out_meta.append(m)
                    if valid_out_meta:
                        out_def["metadata"] = valid_out_meta
                    else:
                        # Delete malformed metadata entirely
                        out_def.pop("metadata", None)
        if removed_count:
            logger.debug(
                f"Sanitized metadata for process '{proc.get('id')}' from provider '{provider_name}': removed {removed_count} malformed entries"
            )
        return proc

    async def fetch_processes_for_provider(
        self, provider_name: str
    ) -> List[ProcessSummary]:
        """Fetch the process list for a single provider.

        Selection rules:
        - Only processes explicitly listed in `providers.yaml` (respecting `exclude=True`) are exposed.
        - Remote processes not configured are ignored (future option `mirror_all_processes` could relax this).
        - Provides curated visibility and avoids surfacing experimental upstream processes accidentally.
        - If UMP_PER_PROCESS_FETCH is true we bypass the bulk list endpoint and fetch
          each configured process individually to obtain richer metadata when list
          responses are sparse.
        """
        cached_processes = self._process_cache.get(provider_name)
        if cached_processes is not None:
            logger.info(
                f"Process list cache hit for provider '{provider_name}': {len(cached_processes)} processes"
            )
            return cached_processes
        else:
            logger.info(f"Process list cache miss for provider '{provider_name}'")

        provider: ProviderConfig = self.provider_config_service.get_provider(
            provider_name
        )
        # build set of explicitly configured ids (excluding those marked exclude)
        configured = self.provider_config_service.get_provider(provider_name).processes
        configured_ids = {p.id for p in configured if not getattr(p, "exclude", False)}

        processes: List[ProcessSummary] = []

        if app_settings.UMP_PER_PROCESS_FETCH:
            # Fetch each configured process individually
            for cid in configured_ids:
                raw_id = cid.split(":", 1)[1] if ":" in cid else cid
                per_url = str(provider.url).rstrip("/") + f"/processes/{raw_id}"
                try:
                    data = await self.http_client.get(per_url)
                    proc = dict(data)
                    # handlers will rewrite id -> canonical provider-prefixed id
                    for handler in self._process_handlers:
                        proc = handler(provider_name, proc)
                    processes.append(ProcessSummary(**proc))
                except Exception as e:
                    logger.warning(
                        f"Failed per-process fetch for '{cid}' from provider '{provider_name}': {e}"
                    )
                    continue
        else:
            # Bulk list followed by filtering
            list_url = str(provider.url).rstrip("/") + "/processes"
            try:
                data = await self.http_client.get(list_url)
                remote_list = data.get("processes", [])
            except Exception as fetch_error:
                if cached_processes is not None:
                    logger.warning(
                        f"Using cached processes for provider {provider_name} due to error fetching list: {fetch_error}"
                    )
                    return cached_processes
                return []

            for raw_proc in remote_list:
                raw_id = raw_proc.get("id")
                if raw_id is None or raw_id not in configured_ids:
                    continue
                proc: Dict[str, Any] = dict(raw_proc)
                try:
                    for handler in self._process_handlers:
                        proc = handler(provider_name, proc)
                    processes.append(ProcessSummary(**proc))
                except ValueError as e:
                    logger.warning(
                        f"Skipping process '{raw_id}' due to handler ValueError: {e}"
                    )
                    continue
                except Exception as handler_error:
                    logger.warning(
                        f"Error processing configured process '{raw_id}' for provider {provider_name}: {handler_error}"
                    )
                    continue

        self._process_cache.set(provider_name, processes)
        logger.debug(
            f"Cached {len(processes)} configured processes for provider '{provider_name}' (strategy={'per-process' if app_settings.UMP_PER_PROCESS_FETCH else 'bulk-list'})"
        )
        return processes

    async def get_all_processes(self) -> ProcessList:
        """
        Fetches processes for all providers concurrently using asyncio.gather.
        Aggregates all results into a single ProcessList.
        """
        provider_names = self.provider_config_service.list_providers()
        # Create a coroutine for each provider
        tasks = [self.fetch_processes_for_provider(name) for name in provider_names]
        # Run all coroutines concurrently
        results = await asyncio.gather(*tasks)
        # Flatten the list of lists into a single list
        all_processes = [proc for sublist in results for proc in sublist]
        return ProcessList(processes=all_processes)

    async def get_process(self, process_id: str) -> Process:
        """
        Retrieve a single process by id. The id may include a provider prefix
        (e.g. 'provider:proc'). If a provider prefix is present we fetch the
        process description directly from that provider. Otherwise we search
        across configured providers for a matching process summary and, if
        possible, attempt to fetch the full description from the provider.
        """
        # First check cache by full process id
        cached = self._process_cache_by_id.get(process_id)
        if cached is not None:
            logger.info(f"Process cache hit for id '{process_id}'")
            return cached
        else:
            logger.info(f"Process cache miss for id '{process_id}'")

        # Try to detect provider prefix
        try:
            provider_prefix, raw_id = self.process_id_validator.extract(process_id)
            # If extract succeeded, attempt to fetch from that provider
            provider = self.provider_config_service.get_provider(provider_prefix)
            url = str(provider.url).rstrip("/") + f"/processes/{raw_id}"
            try:
                data = await self.http_client.get(url)
                # run handlers on returned dict (if any) and return Process model
                proc = dict(data)
                for handler in self._process_handlers:
                    proc = handler(provider_prefix, proc)
                model = Process(**proc)
                # cache under canonical id
                self._process_cache_by_id.set(model.pid, model)
                logger.debug(f"Cached process '{model.pid}' in per-process cache")
                # also cache under bare id for convenience (e.g., 'echo')
                if ":" in model.pid:
                    bare = model.pid.split(":", 1)[1]
                    self._process_cache_by_id.set(bare, model)
                    logger.debug(f"Also cached process under bare id '{bare}'")
                return model
            except OGCProcessException:
                # re-raise to be handled by the web adapter
                raise
            except Exception as fetch_error:
                logger.error(
                    f"Failed to fetch process {process_id} from provider {provider_prefix}: {fetch_error}"
                )
                raise OGCProcessException(
                    OGCExceptionResponse(
                        type="about:blank",
                        title="Upstream Error",
                        status=502,
                        detail=f"Could not retrieve process {process_id} from provider {provider_prefix}",
                        instance=None,
                    )
                )
        except ValueError:
            # No provider prefix — fall back to searching all providers
            all_procs = await self.get_all_processes()
            for proc_summary in all_procs.processes:
                if (
                    proc_summary.pid.endswith(f":{process_id}")
                    or proc_summary.pid == process_id
                ):
                    # Try to fetch full description from provider if link available
                    # Look for a 'self' link or processes/{id} link in summary
                    provider_prefix, _ = self.process_id_validator.extract(
                        proc_summary.pid
                    )
                    provider = self.provider_config_service.get_provider(
                        provider_prefix
                    )
                    # attempt to fetch full description
                    url = str(provider.url).rstrip("/") + f"/processes/{process_id}"
                    try:
                        data = await self.http_client.get(url)
                        proc = dict(data)
                        for handler in self._process_handlers:
                            proc = handler(provider_prefix, proc)
                        model = Process(**proc)
                        self._process_cache_by_id.set(model.pid, model)
                        logger.debug(
                            f"Cached process '{model.pid}' in per-process cache"
                        )
                        if ":" in model.pid:
                            bare = model.pid.split(":", 1)[1]
                            self._process_cache_by_id.set(bare, model)
                            logger.debug(f"Also cached process under bare id '{bare}'")
                        return model
                    except Exception as fetch_error:
                        # If fetching full description fails, but summary has enough data,
                        # construct a Process from the summary (no inputs/outputs)
                        logger.debug(
                            f"Fetching full description failed for '{proc_summary.pid}': {fetch_error} - falling back to summary"
                        )
                        model = Process(**proc_summary.model_dump())
                        self._process_cache_by_id.set(model.pid, model)
                        logger.debug(
                            f"Cached process '{model.pid}' in per-process cache (from summary fallback)"
                        )
                        if ":" in model.pid:
                            bare = model.pid.split(":", 1)[1]
                            self._process_cache_by_id.set(bare, model)
                            logger.debug(
                                f"Also cached process under bare id '{bare}' (from summary fallback)"
                            )
                        return model

            # Not found
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Not Found",
                    status=404,
                    detail=f"Process '{process_id}' not found",
                    instance=None,
                )
            )

    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.http_client.close()

    async def execute_process(self, process_id: str, payload: dict, headers: dict) -> dict:
        """Delegate execution to JobManager (always async semantics Step 1).

        `payload` is the full normalized ExecuteRequest provider payload (includes
        inputs, outputs, response preferences, subscriber callbacks). JobManager
        will decide which parts to persist locally (e.g., inputs metadata) while
        forwarding the entire payload downstream.
        """
        if self.job_manager is None:
            logger.error("JobManager not attached to ProcessManager")
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Server Error",
                    status=500,
                    detail="Contact admin",
                    instance=None,
                )
            )
        return await self.job_manager.create_and_forward(process_id, payload or {}, headers)

    def attach_job_manager(self, job_manager: JobManager) -> None:
        """Attach the JobManager once; explicit wiring keeps type hints simple."""
        self.job_manager = job_manager

