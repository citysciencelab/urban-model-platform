import asyncio
import traceback
from logging import getLogger

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from flask import g

from ump.config import app_settings
from ump.api.models.providers_config import ProcessConfig, ProviderConfig
from ump.api.providers import (
    get_providers,
)
from ump.errors import OGCProcessException
from ump.utils import fetch_json

logger = getLogger(__name__)

#TODO: add validation of loaded processes through pydantic model or existing Process class
async def load_processes():
    processes = []
    
    auth = g.get("auth_token", {}) or {}
    
    # TODO manually parsing jwt is not recommended, use a library like PyJWT or better Authlib 
    realm_roles: list = auth.get("realm_access", {}).get("roles", [])
    
    client_roles: list = (
        auth.get(
            "resource_access", {}
        ).get(
            app_settings.UMP_KEYCLOAK_CLIENT_ID, {}
        ).get(
            "roles", []
        )
    )

    client_timeout = ClientTimeout(
        total=5,  # Set a reasonable timeout for the requests
        connect=2,  # Connection timeout
        sock_connect=2,  # Socket connection timeout
        sock_read=5,  # Socket read timeout
    ) # remote server needs to answer in time, because we make multiple requests!

    async with aiohttp.ClientSession(
        raise_for_status=False, timeout=client_timeout
    ) as session:
        # Create a list of tasks for fetching processes concurrently
        #TODO: it would make more sense if, not all processes are fetched,
        # but only those that are configured and are accessible by the user
        tasks = [
            fetch_provider_processes(
                session, provider_name,
                provider_config, realm_roles, client_roles
            )
            for provider_name, provider_config in get_providers().items()
        ]

        # Run all tasks in an async manner and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, BaseException):
                logger.error("Error fetching processes: %s", result)
            else:
                processes.extend(result)

    return {"processes": processes}


async def fetch_provider_processes(
        session: ClientSession,
        provider_name: str, provider_config: ProviderConfig,
        realm_roles: list, client_roles: list
):
    """Fetch processes for a specific provider and filter them."""
    provider_processes = []
    try:
        provider_auth = authenticate_provider(provider_config)
        
        results = await fetch_json(
            session=session,
            url=f"{provider_config.server_url}processes",
            raise_for_status=True,
            headers={"Content-type": "application/json", "Accept": "application/json"},
            auth=provider_auth
        )

        # TODO: instead of manually checking for a key, we should validate the response
        # using a pydantic model or json schema!
        if "processes" in results:
            for process in results["processes"]:
                process_id = process["id"]
                if process_id not in provider_config.processes:
                    logger.info(
                        "No configuration found for process %s, ignoring it.",
                        process_id
                    )
                    # next process
                    continue

                process_config = provider_config.processes[process_id]
                if has_user_access_rights(
                    process_id, provider_name, process_config,
                    realm_roles, client_roles
                ):
                    process["id"] = f"{provider_name}:{process_id}"
                    provider_processes.append(process)
        else:
            logger.error(
                "The response from the remote service was not valid. "
                "URL: %s, Content: %s",
                provider_config.server_url,
                results
            )

    # Note: fetch_json raises OGCProcessException on errors
    except OGCProcessException as e:
        logger.error("HTTP error while accessing provider %s: %s", provider_name, e)

    except Exception as e:
        logger.error("Unexpected error while processing provider %s: %s", provider_name, e)
        traceback.print_exc()

    return provider_processes


async def fetch_processes_from_provider(session, provider_config, provider_auth):
    """Fetch processes from the provider's API."""
    try:
        response = await session.get(
            f"{provider_config.server_url}processes",
            auth=provider_auth,
            headers={
                "Content-type": "application/json",
                "Accept": "application/json",
            },
            timeout=ClientTimeout(total=provider_config.timeout),
        )
        return await response.json()
    except aiohttp.ClientError as e:
        logger.error(
            "Failed to fetch processes from %s: %s",
            provider_config.server_url,e
        )
        raise

def has_user_access_rights(
    process_id: str,
    provider_name: str,
    process_config: ProcessConfig,
    realm_roles: list[str],
    client_roles: list[str],
) -> bool:
    """
    Determines if a process is visible to the user based on the following checks:
    0. The process is configured to be excluded or not.
    1. Anonymous access is allowed.
    2. The user has access to all processes of a provider(/ModelServer).
    3. The user has access to the specific process.
    """
    # Check if the process is excluded
    if process_config.exclude:
        logger.info("Process ID %s is configured to be excluded.", process_id)
        return False

    # Check provider/ModelServer-level access
    access_to_all_processes_granted = (
        provider_name in realm_roles
        or provider_name in client_roles
    )

    # Check process-specific access
    access_to_this_process_granted = (
        f"{provider_name}_{process_id}" in realm_roles
        or f"{provider_name}_{process_id}" in client_roles
    )

    # Log the specific condition(s) that grant access
    if process_config.anonymous_access:
        logger.info(
            "Granting access for process %s:%s: Anonymous access is allowed.",
            provider_name,
            process_id
        )


    if access_to_all_processes_granted:
        logger.info(
            "Granting access for process %s: User has provider-level access. Role: %s",
            process_id,
            provider_name
        )

    if access_to_this_process_granted:
        logger.info(
            "Granting access for process %s: User has process-specific access. Role: %s_%s",
            process_id,
            provider_name,
            process_id
        )

    # Grant access if any of the conditions are met
    if (
        process_config.anonymous_access
        or access_to_all_processes_granted
        or access_to_this_process_granted
    ):
        return True

    logger.info(
        "Not granting access for process %s", process_id
    )
    return False
