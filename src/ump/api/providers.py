import atexit
import logging
from logging import getLogger
from threading import Lock

import aiohttp
import yaml
from pydantic import ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from ump.api.models.providers_config import (
    ModelServers,
    ProcessConfig,
    ProviderConfig,
    model_servers_adapter,
)
from ump.config import app_settings as config

logger = getLogger(__name__)

PROVIDERS: ModelServers = {}
PROVIDERS_LOCK = Lock()  # Thread-safe lock for updating PROVIDERS


class ProviderLoader(FileSystemEventHandler):
    def on_modified(self, event):
        logger.info("File modified: %s", event.src_path)
        if event.src_path == config.UMP_PROVIDERS_FILE.absolute().as_posix():
            self.load_providers()

    def load_providers(self):
        logger.info("(Re)Loading providers from %s", config.UMP_PROVIDERS_FILE)
        try:
            with open(config.UMP_PROVIDERS_FILE, encoding="UTF-8") as file:
                if content := yaml.safe_load(file):
                    validated_content = model_servers_adapter.validate_python(content)
                    with PROVIDERS_LOCK:  # Ensure thread-safe update
                        # Update PROVIDERS in place
                        PROVIDERS.clear()
                        PROVIDERS.update(validated_content)
                        logger.info("Providers (re)loaded successfully")
        except FileNotFoundError:
            logger.error("Providers file not found: %s", config.UMP_PROVIDERS_FILE)
        except yaml.YAMLError as e:
            logger.error("Failed to parse providers file: %s", e)
        except ValidationError as e:
            logger.error("Validation error in providers file: %s", e)


# Initialize the ProviderLoader and load providers initially
provider_loader = ProviderLoader()
provider_loader.load_providers()  # Trigger initial loading

observer = PollingObserver()
observer.schedule(
    provider_loader,
    config.UMP_PROVIDERS_FILE.absolute().as_posix(),  # Simplified path handling
    recursive=False,
)
observer.start()

# Graceful shutdown for observer
atexit.register(observer.stop)


def get_providers() -> ModelServers:
    return PROVIDERS


def authenticate_provider(provider: ProviderConfig):
    auth = None
    if provider.authentication:
        auth = aiohttp.BasicAuth(
            provider.authentication.user,
            provider.authentication.password.get_secret_value(),
        )
    return auth


def load_process_config(
    provider: str, process_id: str
) -> ProcessConfig:

    with PROVIDERS_LOCK:  # Ensure thread-safe access
        try:
            processes = PROVIDERS[provider].processes
            
            # load process configuration
            process_config: ProcessConfig = processes[process_id]

            if process_config.exclude:
                logger.debug("Excluding process %s based on configuration", process_id)
        except KeyError:
            logger.error(
                "Provider '%s' or process '%s' not found in PROVIDERS",
                provider,
                process_id,
            )
            raise ValueError(
                f"Provider '{provider}' or process '{process_id}' not found"
            )

        return process_config


def check_result_storage(provider, process_id):
    with PROVIDERS_LOCK:  # Ensure thread-safe access
        if provider in PROVIDERS and process_id in PROVIDERS[provider].processes:
            return PROVIDERS[provider].processes[process_id].result_storage
    return None
