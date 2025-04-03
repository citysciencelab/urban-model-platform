import logging

from pydantic import FilePath, HttpUrl, SecretStr, computed_field
from pydantic_settings import BaseSettings
from rich import print

logger = logging.getLogger(__name__)
# using pydantic_settings to manage environment variables
# and do automatic type casting in a central place
class UmpSettings(BaseSettings):
    UMP_LOG_LEVEL: str = "INFO"
    UMP_PROVIDERS_FILE: FilePath = "providers.yaml"
    UMP_API_SERVER_URL: str = "localhost:3000"
    UMP_API_SERVER_WORKERS: int = 4
    UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL: int = 5
    UMP_DATABASE_NAME: str = "ump"
    UMP_DATABASE_HOST: str = "postgres"
    UMP_DATABASE_PORT: int = 5432
    UMP_DATABASE_USER: str = "postgres"
    UMP_DATABASE_PASSWORD: SecretStr = "postgres"
    UMP_GEOSERVER_URL: HttpUrl | None = HttpUrl("http://geoserver:8080/geoserver")
    UMP_GEOSERVER_DB_HOST: str = "postgis"
    UMP_GEOSERVER_DB_PORT: int = 5432
    UMP_GEOSERVER_DB_NAME: str = "ump"
    UMP_GEOSERVER_DB_USER: str = "ump"
    UMP_GEOSERVER_DB_PASSWORD: SecretStr = "ump"
    UMP_GEOSERVER_WORKSPACE_NAME: str = "UMP"
    UMP_GEOSERVER_USER: str = "geoserver"
    UMP_GEOSERVER_PASSWORD: SecretStr = "geoserver"
    UMP_GEOSERVER_CONNECTION_TIMEOUT: int = 60 # seconds
    UMP_JOB_DELETE_INTERVAL: int = 240 # minutes
    UMP_KEYCLOAK_URL: HttpUrl = "http://keycloak:8080/auth"
    UMP_KEYCLOAK_REALM: str = "UrbanModelPlatform"
    UMP_KEYCLOAK_CLIENT_ID: str = "ump-client"
    UMP_KEYCLOAK_USER: str = "admin"
    UMP_KEYCLOAK_PASSWORD: SecretStr = "admin"

    @computed_field
    @property
    def UMP_GEOSERVER_URL_REST(self) -> HttpUrl:
        """Constructs the full URL for the GeoServer REST API"""
        return HttpUrl(str(self.UMP_GEOSERVER_URL) + "/rest")

    @computed_field
    @property
    def UMP_GEOSERVER_URL_WORKSPACE(self) -> HttpUrl:
        """Constructs the full URL for the GeoServer workspace"""
        return HttpUrl(str(self.UMP_GEOSERVER_URL) + "/rest/workspaces")

    def print_settings(self):
        """Prints the settings for debugging purposes"""
        logger.info("UMP Settings:")
        print(self)


app_settings = UmpSettings()
app_settings.print_settings()
