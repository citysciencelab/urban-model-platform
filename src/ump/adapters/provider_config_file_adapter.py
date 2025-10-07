from watchdog.events import FileSystemEventHandler


import threading
import yaml
import os
from typing import List, Optional
from pydantic import ValidationError
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from ump.core.interfaces.provider_config import ProviderConfigPort
from ump.core.models.providers_config import ProviderConfig, ProcessConfig, ModelServers, model_servers_adapter

import time
from threading import Timer

class _ConfigFileHandler(FileSystemEventHandler):
    DEBOUNCE_DELAY = 0.5  # 500ms

    def __init__(self, adapter, config_path, config_filename):
        self.adapter = adapter
        self.config_path = os.path.abspath(config_path)
        self.config_filename = config_filename
        self._reload_timer = None

    def on_any_event(self, event):
        if event.is_directory:
            return
        src_path = str(event.src_path)
        # Robust checks for configmap updates (Kubernetes)
        if (
            src_path == self.config_path or
            src_path.endswith(self.config_filename) or
            '..data' in src_path
        ):
            self._debounced_reload()

    def _debounced_reload(self):
        if self._reload_timer:
            self._reload_timer.cancel()
        self._reload_timer = Timer(self.DEBOUNCE_DELAY, self.adapter._load_providers)
        self._reload_timer.start()


class ProviderConfigFileAdapter(ProviderConfigPort):
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._lock = threading.Lock()
        self._providers: ModelServers = {}
        self._load_providers()

    def start_file_watcher(self):
        observer = PollingObserver()
        config_dir = os.path.dirname(self._config_path)
        config_filename = os.path.basename(self._config_path)
        handler = _ConfigFileHandler(self, self._config_path, config_filename)
        observer.schedule(handler, path=config_dir, recursive=False)
        observer.start()
        self._observer = observer

    def stop_file_watcher(self):
        if hasattr(self, '_observer'):
            self._observer.stop()
            self._observer.join()

    def _atomic_update(self, new_providers: ModelServers):
        """
        Atomar und thread-safe die Provider-Konfiguration aktualisieren, bei Fehlern Rollback.
        """
        with self._lock:
            old_providers = self._providers.copy()
            try:
                # Deep copy der neuen Provider-Konfiguration
                self._providers = {name: provider.model_copy(deep=True) for name, provider in new_providers.items()}
            except Exception as e:
                self._providers = old_providers
                raise e

    def _load_providers(self):
        with self._lock:
            try:
                with open(self._config_path, encoding="UTF-8") as file:
                    content = yaml.safe_load(file)
                    if content:
                        validated = model_servers_adapter.validate_python(content)
                        self._atomic_update(validated)
            except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
                # Log error or handle as needed
                self._providers = {}

    def get_providers(self) -> List[ProviderConfig]:
        with self._lock:
            return list(self._providers.values())

    def get_provider(self, provider_name: str) -> Optional[ProviderConfig]:
        with self._lock:
            return self._providers.get(provider_name)

    def get_process_config(self, provider_name: str, process_id: str) -> Optional[ProcessConfig]:
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider and process_id in provider.processes:
                return provider.processes[process_id]
            return None

    def list_providers(self) -> List[str]:
        with self._lock:
            return list(self._providers.keys())

    def list_processes(self, provider_name: str) -> List[str]:
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider:
                return list(provider.processes.keys())
            return []

    def check_process_availability(self, provider_name: str, process_id: str) -> bool:
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider and process_id in provider.processes:
                return not provider.processes[process_id].exclude
            return False
