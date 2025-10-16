# ump/core/managers/process_manager.py
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.models.process import ProcessList, ProcessSummary
from ump.core.models.link import Link
from ump.core.utils.link_rewriter import rewrite_links_to_local
from ump.core.settings import app_settings
from ump.core.models.providers_config import ProviderConfig
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.managers.process_cache import ProcessListCache
from ump.core.managers.process_cache import ProcessCache

from ump.core.settings import logger
import asyncio
import time
from typing import List, Callable, Dict, Any
from ump.core.models.process import Process
from ump.core.models.ogcp_exception import OGCExceptionResponse
from ump.core.exceptions import OGCProcessException

class ProcessManager(ProcessesPort):
    def __init__(
        self, 
        provider_config_service: ProvidersPort,
        http_client: HttpClientPort,
        process_id_validator: ProcessIdValidatorPort,
        cache_expiry_seconds: int = 300
    ) -> None:
        self.provider_config_service = provider_config_service
        self.http_client = http_client
        self.process_id_validator = process_id_validator
        self._process_cache = ProcessListCache[ProcessSummary](expiry_seconds=cache_expiry_seconds)
        # cache individual process descriptions by id
        self._process_cache_by_id = ProcessCache[Process](expiry_seconds=cache_expiry_seconds)

        # A pipeline of handlers (functions) that transform a fetched process dict.
        # Each handler has signature: handler(provider_name: str, proc: Dict[str, Any]) -> Dict[str, Any]
        # Handlers can raise ValueError to indicate the process should be skipped.
        self._process_handlers: List[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = [
            self._handle_process_id,
            self._handle_rewrite_links,
        ]

    def add_process_handler(self, handler: Callable[[str, Dict[str, Any]], Dict[str, Any]]):
        """Register an additional process handler at runtime."""
        self._process_handlers.append(handler)

    # --- Default handlers -------------------------------------------------
    def _handle_process_id(self, provider_name: str, proc: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce and create the canonical process id using the injected validator.

        Raises ValueError if the id cannot be created/validated.
        """
        raw_proc_id = proc.get("id")
        if raw_proc_id is None:
            raise ValueError("missing process id")
        full_proc_id = self.process_id_validator.create(provider_name, raw_proc_id)
        proc["id"] = full_proc_id
        return proc

    def _handle_rewrite_links(self, provider_name: str, proc: Dict[str, Any]) -> Dict[str, Any]:
        """Rewrite remote links to local links if enabled in settings.
        This handler is a no-op if links are missing or rewriting is disabled.
        """
        from ump.core.settings import app_settings
        if not app_settings.UMP_REWRITE_REMOTE_LINKS:
            return proc

        if "links" not in proc or not isinstance(proc.get("links"), list):
            return proc
        try:
            from ump.core.models.link import Link
            from ump.core.utils.link_rewriter import rewrite_links_to_local

            proc_links = [Link(**l) for l in proc.get("links", [])]
            proc["links"] = [l.model_dump() for l in rewrite_links_to_local(str(proc.get("id")), proc_links)]
        except Exception:
            logger.warning(f"Failed to rewrite links for process {proc.get('id')}")
            # leave them empty
            proc["links"] = []

        return proc

    async def fetch_processes_for_provider(self, provider_name: str) -> List[ProcessSummary]:
        """
        Fetches the process list for a single provider asynchronously.
        Uses ProcessCache for caching.
        Returns a list of Process objects for that provider.
        """
        cached_processes = self._process_cache.get(provider_name)
        if cached_processes is not None:
            logger.info(f"Process list cache hit for provider '{provider_name}': {len(cached_processes)} processes")
            return cached_processes
        else:
            logger.info(f"Process list cache miss for provider '{provider_name}'")

        provider: ProviderConfig = self.provider_config_service.get_provider(provider_name)
        url = str(provider.url).rstrip("/") + "/processes"
        
        try:
            # Fetch process metadata from remote provider
            data = await self.http_client.get(url, timeout=provider.timeout)
            processes = []
            
            for raw_proc in data.get("processes", []):
                # make a shallow copy so handlers can mutate safely
                proc: Dict[str, Any] = dict(raw_proc)
                try:
                    # Run the registered handler pipeline. Handlers may raise
                    # ValueError to indicate the process should be skipped.
                    for handler in self._process_handlers:
                        proc = handler(provider_name, proc)

                    processes.append(ProcessSummary(**proc))
                except ValueError:
                    # Handler indicated to skip this process (e.g. invalid id)
                    continue
                except Exception as e:
                    # Log unexpected handler errors and skip the process
                    logger.warning(
                        f"Error processing fetched process for provider {provider_name}: {e}"
                    )
                    continue
            # Store in cache
            self._process_cache.set(provider_name, processes)
            logger.debug(f"Cached {len(processes)} processes for provider '{provider_name}'")

            return processes
        except Exception as e:
            # On error, return cached data if available
            if cached_processes is not None:
                # Optionally log warning about fallback
                logger.warning(f"Using cached processes for provider {provider_name} due to error: {e}")
                return cached_processes
            # logger.error(f"Failed to fetch processes for provider {provider_name}: {e}")
            return []

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
                data = await self.http_client.get(url, timeout=provider.timeout)
                # run handlers on returned dict (if any) and return Process model
                proc = dict(data)
                for handler in self._process_handlers:
                    proc = handler(provider_prefix, proc)
                model = Process(**proc)
                # cache under canonical id
                self._process_cache_by_id.set(model.id, model)
                logger.debug(f"Cached process '{model.id}' in per-process cache")
                # also cache under bare id for convenience (e.g., 'echo')
                if ":" in model.id:
                    bare = model.id.split(":", 1)[1]
                    self._process_cache_by_id.set(bare, model)
                    logger.debug(f"Also cached process under bare id '{bare}'")
                return model
            except OGCProcessException:
                # re-raise to be handled by the web adapter
                raise
            except Exception as e:
                logger.error(f"Failed to fetch process {process_id} from provider {provider_prefix}: {e}")
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
                if proc_summary.id.endswith(f":{process_id}") or proc_summary.id == process_id:
                    # Try to fetch full description from provider if link available
                    # Look for a 'self' link or processes/{id} link in summary
                    provider_prefix, _ = self.process_id_validator.extract(proc_summary.id)
                    provider = self.provider_config_service.get_provider(provider_prefix)
                    # attempt to fetch full description
                    url = str(provider.url).rstrip("/") + f"/processes/{process_id}"
                    try:
                        data = await self.http_client.get(url, timeout=provider.timeout)
                        proc = dict(data)
                        for handler in self._process_handlers:
                            proc = handler(provider_prefix, proc)
                        model = Process(**proc)
                        self._process_cache_by_id.set(model.id, model)
                        logger.debug(f"Cached process '{model.id}' in per-process cache")
                        if ":" in model.id:
                            bare = model.id.split(":", 1)[1]
                            self._process_cache_by_id.set(bare, model)
                            logger.debug(f"Also cached process under bare id '{bare}'")
                        return model
                    except Exception:
                        # If fetching full description fails, but summary has enough data,
                        # construct a Process from the summary (no inputs/outputs)
                        model = Process(**proc_summary.model_dump())
                        self._process_cache_by_id.set(model.id, model)
                        logger.debug(f"Cached process '{model.id}' in per-process cache (from summary fallback)")
                        if ":" in model.id:
                            bare = model.id.split(":", 1)[1]
                            self._process_cache_by_id.set(bare, model)
                            logger.debug(f"Also cached process under bare id '{bare}' (from summary fallback)")
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
