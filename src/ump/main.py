# main.py
import os

from ump.adapters.aiohttp_client_adapter import AioHttpClientAdapter
from ump.adapters.colon_process_id_validator import ColonProcessId
import uvicorn

from ump.adapters.provider_config_file_adapter import ProviderConfigFileAdapter
from ump.adapters.web.fastapi import create_app
from ump.core.settings import logger

# main lives at the outermost layer (not in core)
# Instantiates all the concrete adapters
# Wires dependencies together
# Starts the application

def main():
    config_path = os.path.join(os.path.dirname(__file__), "../../providers.yaml")
    config_path = os.path.abspath(config_path)

    provider_config_adapter = ProviderConfigFileAdapter(config_path)
    provider_config_adapter.start_file_watcher()

    logger.info("Starting UMP FastAPI application...")
    
    # Create app with lifespan that manages the http client
    # injecting necessary dependencies
    app = create_app(
        provider_config_adapter,
        AioHttpClientAdapter(),
        ColonProcessId()
    )

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
