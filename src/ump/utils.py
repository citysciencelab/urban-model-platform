import asyncio
import logging

import aiohttp

from ump.api.models.ogc_exception import OGCExceptionResponse
from ump.errors import OGCProcessException


logger = logging.getLogger(__name__)

def join_url_parts(*parts):
    return '/'.join(str(part).strip('/') for part in parts if part != '')

async def fetch_response_content(
        response: aiohttp.ClientResponse
) -> tuple[str | dict, str, int]:
    """
    Reads the content of an aiohttp response, handling both JSON and text,
    regardless of HTTP status code.
    Returns a tuple: (content, content_type, status_code)
    """
    content_type = response.headers.get("Content-Type", "")
    status = response.status

    try:
        if "application/json" in content_type:
            content = await response.json()
        else:
            content = await response.text()
    except Exception:
        # If JSON parsing fails, fallback to text
        content = await response.text()
        content_type = "text/plain"

    return content, content_type, status

# TODO: retry on timeouts, connection errors, etc.
async def fetch_json(
        session: aiohttp.ClientSession, url,
        raise_for_status=False, **kwargs
) -> dict:
    try:
        async with session.get(url, **kwargs) as response:
            try:
                response_data = await response.json()
                
                if raise_for_status:
                    response.raise_for_status()

                return response_data

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
                detail=f"The remote service returned an HTTP error: {response_data}",
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