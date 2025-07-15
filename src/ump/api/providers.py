import atexit
import time
from logging import getLogger
from threading import Lock, Timer
import threading
from typing import Optional

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

# Thread-safe provider storage
PROVIDERS: ModelServers = {}
PROVIDERS_LOCK = Lock()
RELOAD_TIMER: Optional[Timer] = None
DEBOUNCE_DELAY = 0.5  # 500ms debounce


class ProviderLoader(FileSystemEventHandler):
    def __init__(self):
        self.last_reload = 0
        self.reload_lock = threading.Lock()

    # need to listen on any event, not just file changes for k8s configmap updates
    def on_any_event(self, event):
        # Ignore directory events
        if event.is_directory:
            return
            
        logger.info("File event: %s on %s", event.event_type, event.src_path)

        event.src_path = str(event.src_path)
        
        # Check if the event affects our config file
        config_path = config.UMP_PROVIDERS_FILE.absolute().as_posix()

        endswith = event.src_path.endswith(config.UMP_PROVIDERS_FILE.name)
        contains = '..data' in event.src_path
        
        if (
            event.src_path == config_path or
            endswith or
            contains
        ):
            self._debounced_reload()

    def _debounced_reload(self):
        """Debounce rapid file changes to avoid reload storms"""
        global RELOAD_TIMER
        
        # Cancel existing timer
        if RELOAD_TIMER:
            RELOAD_TIMER.cancel()
        
        # Schedule debounced reload
        RELOAD_TIMER = Timer(DEBOUNCE_DELAY, self.load_providers)
        RELOAD_TIMER.start()

    def load_providers(self):
        logger.info("(Re)Loading providers from %s", config.UMP_PROVIDERS_FILE)
        
        # Create new providers dict (don't modify global state yet)
        new_providers = {}
        
        try:
            with open(config.UMP_PROVIDERS_FILE, encoding="UTF-8") as file:
                if content := yaml.safe_load(file):
                    # Validate before applying
                    validated_content = model_servers_adapter.validate_python(content)
                    new_providers.update(validated_content)
                    
                    # Atomic update with rollback capability
                    self._atomic_update(new_providers)
                    logger.info("Providers (re)loaded successfully")
                else:
                    logger.warning("Providers file is empty, keeping current configuration")
                    
        except FileNotFoundError:
            logger.error("Providers file not found: %s", config.UMP_PROVIDERS_FILE)
        except yaml.YAMLError as e:
            logger.error("Failed to parse providers file: %s", e)
        except ValidationError as e:
            logger.error("Validation error in providers file: %s", e)
        except Exception as e:
            logger.error("Unexpected error loading providers: %s", e)

    def _atomic_update(self, new_providers: ModelServers):
        """Atomically update providers with rollback capability"""
        global PROVIDERS
        
        with PROVIDERS_LOCK:
            # Store old providers for potential rollback
            old_providers = PROVIDERS
        try:
            # Create a new dict with copied Pydantic models
            PROVIDERS = {
                name: provider.model_copy(deep=True) 
                for name, provider in new_providers.items()
            }
        except Exception as e:
            PROVIDERS = old_providers
            raise


# Initialize the ProviderLoader and load providers initially
provider_loader = ProviderLoader()
provider_loader.load_providers()  # Trigger initial loading

observer = PollingObserver()
observer.schedule(
    provider_loader,
    config.UMP_PROVIDERS_FILE.parent.as_posix(),  # Watch directory, not file
    recursive=False
)
observer.start()

def cleanup():
    """Cleanup function for graceful shutdown"""
    global RELOAD_TIMER
    
    if RELOAD_TIMER:
        RELOAD_TIMER.cancel()
    
    observer.stop()
    observer.join(timeout=5)  # Give it 5 seconds to stop gracefully

# Graceful shutdown for observer
atexit.register(cleanup)


def get_providers() -> ModelServers:
    """Get a copy of current providers (thread-safe and immutable)"""
    with PROVIDERS_LOCK:
        return PROVIDERS.copy()


def get_provider(provider_name: str) -> Optional[ProviderConfig]:
    """Get a specific provider by name (thread-safe)"""
    with PROVIDERS_LOCK:
        return PROVIDERS.get(provider_name)


def authenticate_provider(provider: ProviderConfig):
    """Create authentication object for a provider"""
    auth = None
    if provider.authentication:
        auth = aiohttp.BasicAuth(
            provider.authentication.user, 
            provider.authentication.password.get_secret_value()
        )
    return auth


def check_process_availability(provider: str, process_id: str) -> bool:
    """Check if a process is available and not excluded"""
    with PROVIDERS_LOCK:
        if (
            provider in PROVIDERS and 
            process_id in PROVIDERS[provider].processes
        ):
            process: ProcessConfig = PROVIDERS[provider].processes[process_id]
            available = not process.exclude
            
            if process.exclude:
                logger.debug("Excluding process %s based on configuration", process_id)
            
            return available
    
    return False


def check_result_storage(provider: str, process_id: str) -> Optional[str]:
    """Get the result storage type for a process"""
    with PROVIDERS_LOCK:
        if (
            provider in PROVIDERS
            and process_id in PROVIDERS[provider].processes
        ):
            return PROVIDERS[provider].processes[process_id].result_storage
    return None


def get_process_config(provider: str, process_id: str) -> Optional[ProcessConfig]:
    """Get complete process configuration"""
    with PROVIDERS_LOCK:
        if (
            provider in PROVIDERS
            and process_id in PROVIDERS[provider].processes
        ):
            return PROVIDERS[provider].processes[process_id]
    
    raise ValueError(
        f"Process '{process_id}' not found for provider '{provider}'"
    )


def list_providers() -> list[str]:
    """Get list of all provider names"""
    with PROVIDERS_LOCK:
        return list(PROVIDERS.keys())


def list_processes(provider: str) -> list[str]:
    """Get list of all process IDs for a provider"""
    with PROVIDERS_LOCK:
        if provider in PROVIDERS:
            return list(PROVIDERS[provider].processes.keys())
    return []


# Health check function
def is_healthy() -> bool:
    """Check if the provider loader is healthy"""
    with PROVIDERS_LOCK:
        return len(PROVIDERS) > 0 and observer.is_alive()