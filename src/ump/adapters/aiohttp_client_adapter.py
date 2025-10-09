# ump/adapters/aiohttp_client_adapter.py
import asyncio
import aiohttp
from typing import Any, Dict, Optional

from ump.core.interfaces.http_client import HttpClientPort
from ump.core.exceptions import OGCProcessException, OGCExceptionResponse
from ump.core.settings import logger


class AioHttpClientAdapter(HttpClientPort):
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False
    
    async def get(self, url: str, timeout: float) -> Dict[str, Any]:
        if self._session is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with' context manager.")
        
        return await self._fetch_json(
            url, 
            timeout=aiohttp.ClientTimeout(total=timeout),
            raise_for_status=True
        )
    
    async def _fetch_json(
        self, 
        url: str,
        raise_for_status: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch JSON from URL with OGC API-specific error handling.
        
        Translates HTTP/network errors into domain-specific OGCProcessException.
        """
        try:
            async with self._session.get(url, **kwargs) as response:
                try:
                    # Is the response JSON?
                    response_data = await response.json()

                except aiohttp.ContentTypeError:
                    text = await response.text()
                    logger.error(
                        "Invalid JSON response from remote service. URL: %s, Content: %s",
                        url, text[:500]
                    )
                    raise OGCProcessException(
                        OGCExceptionResponse(
                            type="about:blank",
                            title="Invalid Response Content",
                            status=502,
                            detail=(
                                "The response from the remote service was not "
                                f"valid JSON: '{text[:100]}'"
                            ),
                            instance=None
                        )
                    )
                
                # Is the response ok?
                if raise_for_status:
                    response.raise_for_status()

                return response_data

        except asyncio.TimeoutError:
            logger.error(
                "Timeout when requesting remote service. URL: %s",
                url
            )
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Upstream Timeout",
                    status=504,
                    detail="The request to the remote service timed out.",
                    instance=None
                )
            )
        
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                logger.warning(
                    "Authentication failed when requesting remote service. URL: %s, Error: %s",
                    url, str(e)
                )
                raise OGCProcessException(
                    OGCExceptionResponse(
                        type="about:blank",
                        title="Authentication Failed",
                        status=401,
                        detail="Authentication with the remote service failed.",
                        instance=None
                    )
                )
            logger.error(
                "HTTP error when requesting remote service. URL: %s, Status: %s, Error: %s",
                url, e.status, str(e)
            )
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Upstream HTTP Error",
                    status=e.status,
                    detail=f"The remote service returned an HTTP error: {e.status}",
                    instance=None
                )
            )
        
        except aiohttp.ClientError as e:
            logger.error(
                "Connection error when requesting remote service. URL: %s, Error: %s",
                url, str(e)
            )
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Upstream Connection Error",
                    status=502,
                    detail="There was a connection error with the remote service.",
                    instance=None
                )
            )
        
        except Exception as e:
            logger.error(
                "Unexpected error for remote service. URL: %s, Error: %s",
                url, str(e)
            )
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Internal Server Error",
                    status=500,
                    detail="An unexpected error occurred while processing your request.",
                    instance=None
                )
            )
    
    async def close(self) -> None:
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
