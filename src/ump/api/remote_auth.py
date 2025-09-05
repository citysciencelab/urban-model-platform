from typing import Dict, Type
from ump.api.models.providers_config import ApiKeyAuthConfig, AuthConfig, BasicAuthConfig


class AuthStrategy:
    def get_auth(self) -> 'ProviderAuth':
        raise NotImplementedError

class ProviderAuth:
    def __init__(self, auth=None, headers=None):
        self.auth = auth
        self.headers = headers or {}

class NoAuthStrategy(AuthStrategy):
    def get_auth(self) -> ProviderAuth:
        return ProviderAuth()

class BasicAuthStrategy(AuthStrategy):
    def __init__(self, config: BasicAuthConfig):
        self.config = config

    def get_auth(self) -> ProviderAuth:
        import aiohttp
        return ProviderAuth(auth=aiohttp.BasicAuth(self.config.user, self.config.password.get_secret_value()))

class ApiKeyAuthStrategy(AuthStrategy):
    def __init__(self, config: ApiKeyAuthConfig):
        self.config = config

    def get_auth(self) -> ProviderAuth:
        # Returns headers dict for API key
        return ProviderAuth(headers={self.config.key_name: self.config.key_value.get_secret_value()})

AUTH_STRATEGY_REGISTRY: Dict[str, Type[AuthStrategy]] = {
    "BasicAuth": BasicAuthStrategy,
    "ApiKey": ApiKeyAuthStrategy,
    "NoAuth": NoAuthStrategy,  # No authentication
}

def get_auth_strategy(auth_config: AuthConfig) -> AuthStrategy:

    if auth_config is None:
        # No authentication details provided, use NoAuthStrategy
        return NoAuthStrategy()
    
    strategy_cls = AUTH_STRATEGY_REGISTRY.get(auth_config.type)
    
    if not strategy_cls:
        raise ValueError(f"Unknown auth type: {auth_config.type}")

    return strategy_cls()
