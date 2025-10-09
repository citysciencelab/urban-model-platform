# Main entrypoint for UMP app
import os

import uvicorn

from ump.adapters.provider_config_file_adapter import ProviderConfigFileAdapter
from ump.adapters.web.fastapi import create_app
from ump.core.managers.process_manager import ProcessManager
from ump.core.settings import logger


def main():
    # Path to providers.yaml (adjust as needed)
    config_path = os.path.join(os.path.dirname(__file__), "../../providers.yaml")
    config_path = os.path.abspath(config_path)

    # Instantiate provider config adapter
    provider_config_adapter = ProviderConfigFileAdapter(config_path)
    provider_config_adapter.start_file_watcher()

    # Instantiate process manager (implements ProcessesPort)
    process_manager = ProcessManager(provider_config_adapter)

    # Create FastAPI app, injecting process_manager
    logger.info("Starting UMP FastAPI application...")
    app = create_app(process_manager)

    # Run app (FastAPI)

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
