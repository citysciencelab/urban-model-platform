import logging
import traceback

import aiohttp
from aiohttp import ClientTimeout
from flask import g

import ump.api.providers as providers


async def all_processes():
    processes = {}
    async with aiohttp.ClientSession() as session:
        for provider in providers.PROVIDERS:
            try:
                p = providers.PROVIDERS[provider]

                auth = providers.authenticate_provider(p)
                timeout_value = int(p.get("timeout"))

                response = await session.get(
                    f"{p['url']}/processes",
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=ClientTimeout(total=timeout_value / 1000),
                )
                async with response:
                    assert (
                        response.status == 200
                    ), f"Response status {response.status}, {response.reason}"
                    results = await response.json()

                    if "processes" in results:
                        processes[provider] = results["processes"]

            except Exception as e:
                logging.error(
                    "Cannot access %s provider at url \"%s/processes\"! %s",
                    provider,
                    p['url'],
                    e
                )
                traceback.print_exc()
                processes[provider] = []

    return _processes_list(processes)


def _processes_list(results):
    processes = []
    auth = g.get("auth_token", {}) or {}
    realm_roles = auth.get("realm_access", {}).get("roles", [])
    client_roles = (
        auth.get("resource_access", {}).get("ump-client", {}).get("roles", [])
    )

    for provider in providers.PROVIDERS:
        provider_access = provider in realm_roles or provider in client_roles
        if provider_access:
            logging.debug("Granting access for model server %s", provider)
        try:
            # Check if process has special configuration
            for process in results[provider]:
                process_id = f"{provider}_{process['id']}"
                process_access = process_id in realm_roles or process_id in client_roles
                if not process['id'] in providers.PROVIDERS[provider]["processes"]:
                    logging.debug("No configuration found for process %s", process['id'])
                    continue
                process_config = providers.PROVIDERS[provider]["processes"][process['id']]
                public_access = 'anonymous-access' in process_config and process_config['anonymous-access']
                if public_access or process_access or provider_access:
                    logging.debug("Granting access for process %s", process['id'])

                if not public_access and not provider_access and not process_access:
                    logging.debug("Not granting access for %s", process['id'])
                    continue

                logging.debug(
                    "Checking process %s of provider %s",
                    process['id'],
                    providers.PROVIDERS[provider]['name']
                )

                if providers.check_process_availability(provider, process["id"]):
                    process["id"] = f"{provider}:{process['id']}"
                    processes.append(process)

                else:
                    logging.debug("Process ID %s is not configured.", process['id'])
                    continue

        except Exception as e:
            logging.error(
                "Something seems to be wrong with the configuration of model servers: %s",
                e
            )
            traceback.print_exc()

    return {"processes": processes}
