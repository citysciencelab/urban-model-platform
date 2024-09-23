import logging
import traceback

import aiohttp
from flask import g

import ump.api.providers as providers


async def all_processes():
    processes = {}
    async with aiohttp.ClientSession() as session:
        for provider in providers.PROVIDERS:
            try:
                p = providers.PROVIDERS[provider]

                auth = providers.authenticate_provider(p)

                response = await session.get(
                    f"{p['url']}/processes",
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                )
                async with response:
                    assert (
                        response.status == 200
                    ), f"Response status {response.status}, {response.reason}"
                    results = await response.json()

                    if "processes" in results:
                        processes[provider] = results["processes"]

            except Exception as e:
                logging.error(f"Cannot access {provider} provider! {e}")
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
        public_access = not "authentication" in providers.PROVIDERS[provider]
        provider_access = provider in realm_roles or provider in client_roles
        if public_access or provider_access:
            logging.debug(f"Granting access for model server {provider}")
        try:
            # Check if process has special configuration
            for process in results[provider]:
                process_id = f"{provider}_{process['id']}"
                process_access = process_id in realm_roles or process_id in client_roles
                if public_access or process_access or provider_access:
                    logging.debug(f"Granting access for process {process['id']}")

                if not public_access and not provider_access and not process_access:
                    logging.debug(f"Not granting access for {process['id']}")
                    continue

                logging.debug(
                    f"Checking process {process['id']} of provider {providers.PROVIDERS[provider]['name']} "
                )

                if providers.check_process_availability(provider, process["id"]):
                    process["id"] = f"{provider}:{process['id']}"
                    processes.append(process)

                else:
                    logging.debug(f"Process ID  {process['id']} is not configured.")
                    continue

        except Exception as e:
            logging.error(
                f"Something seems to be wrong with the configuration of model servers: {e}"
            )
            traceback.print_exc()

    return {"processes": processes}
