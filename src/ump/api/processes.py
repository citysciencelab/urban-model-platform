import logging
import traceback

import aiohttp
import yaml

import ump.config as config

PROVIDERS: dict = {}

with open(config.PROVIDERS_FILE) as file:
    if content := yaml.safe_load(file):
        PROVIDERS.update(content)


async def all_processes():
    processes = {}
    async with aiohttp.ClientSession() as session:
        for provider in PROVIDERS:
            try:
                p = PROVIDERS[provider]

                # Check for Authentification
                auth = None
                if "authentication" in p:
                    if p["authentication"]["type"] == "BasicAuth":
                        auth = aiohttp.BasicAuth(
                            p["authentication"]["user"], p["authentication"]["password"]
                        )

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
    for provider in PROVIDERS:

        try:

            # Check if process has special configuration
            for process in results[provider]:

                logging.debug(
                    f"Checking  process {process['id']} of provider {PROVIDERS[provider]['name']} "
                )

                for provider_process in PROVIDERS[provider]["processes"]:

                    # Check if process is configured
                    if process["id"] in provider_process.keys():
                        logging.debug(f"Process ID  {process['id']} is configured.")

                        exclude = False

                        # Check if process has special configuration
                        for config in provider_process[process["id"]]:

                            # Check if process should be excluded
                            if "exclude" in config and config["exclude"]:
                                logging.debug(
                                    f"Excluding process {process['id']} based on configuration"
                                )
                                exclude = True

                        if not exclude:
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
