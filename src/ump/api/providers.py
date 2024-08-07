import logging
import traceback

import aiohttp
import yaml

import ump.config as config

PROVIDERS: dict = {}

with open(config.PROVIDERS_FILE) as file:
    if content := yaml.safe_load(file):
        PROVIDERS.update(content)


def authenticate_provider(p):
    auth = None
    if "authentication" in p:
        if p["authentication"]["type"] == "BasicAuth":
            auth = aiohttp.BasicAuth(
                p["authentication"]["user"], p["authentication"]["password"]
            )
    return auth
