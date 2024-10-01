import logging
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import aiohttp
import yaml

import ump.config as config

PROVIDERS: dict = {}

with open(config.PROVIDERS_FILE) as file:
    if content := yaml.safe_load(file):
        PROVIDERS.update(content)

class ProviderLoader(FileSystemEventHandler):
    def on_modified(event):
        if event.src_path == config.PROVIDERS_FILE:
            with open(config.PROVIDERS_FILE) as file:
                if content := yaml.safe_load(file):
                    PROVIDERS.update(content)

observer = Observer()
observer.schedule(ProviderLoader(), os.path.dirname(config.PROVIDERS_FILE), recursive=False)
observer.start()

def authenticate_provider(p):
    auth = None
    if "authentication" in p:
        if p["authentication"]["type"] == "BasicAuth":
            auth = aiohttp.BasicAuth(
                p["authentication"]["user"], p["authentication"]["password"]
            )
    return auth


def check_process_availability(provider, process_id):

    available = False

    if provider in PROVIDERS and process_id in PROVIDERS[provider]["processes"]:
        available = True

        if "exclude" in PROVIDERS[provider]["processes"][process_id]:
            logging.debug(f"Excluding process {process_id} based on configuration")
            available = False

    return available


def check_result_storage(provider, process_id):
    return PROVIDERS.get(provider, {}).get("processes", {}).get(process_id, {}).get("result-storage", None)
