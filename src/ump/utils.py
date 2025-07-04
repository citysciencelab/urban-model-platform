import asyncio
import aiohttp

from ump.api.models.ogc_exception import OGCExceptionResponse
from ump.errors import OGCProcessException


async def fetch_json(session, url, **kwargs):
    try:
        async with session.get(url, **kwargs) as response:
            response.raise_for_status()
            try:
                return await response.json()
            except aiohttp.ContentTypeError:
                # Not JSON
                text = await response.text()
                raise OGCProcessException(
                    OGCExceptionResponse(
                        type="about:blank",
                        title="Invalid Response Content",
                        status=502,
                        detail=f"Response from {url} is not valid JSON. Content: {text[:200]}",
                        instance=url
                    )
                )
    except asyncio.TimeoutError:
        raise OGCProcessException(
            OGCExceptionResponse(
                type="about:blank",
                title="Upstream Timeout",
                status=504,
                detail=f"Request to {url} timed out.",
                instance=url
            )
        )
    except aiohttp.ClientError as e:
        raise OGCProcessException(
            OGCExceptionResponse(
                type="about:blank",
                title="Upstream Connection Error",
                status=502,
                detail=f"Error connecting to {url}: {str(e)}",
                instance=url
            )
        )
    except Exception as e:
        raise OGCProcessException(
            OGCExceptionResponse(
                type="about:blank",
                title="Internal Server Error",
                status=500,
                detail=f"Unexpected error for {url}: {str(e)}",
                instance=url
            )
        )