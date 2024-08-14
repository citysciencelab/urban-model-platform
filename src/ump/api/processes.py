import logging
import traceback

import aiohttp
import yaml

import ump.api.providers as providers
import ump.config as config


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
    for provider in providers.PROVIDERS:

        try:

            # Check if process has special configuration
            for process in results[provider]:

                logging.debug(
                    f"Checking  process {process['id']} of provider {providers.PROVIDERS[provider]['name']} "
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
