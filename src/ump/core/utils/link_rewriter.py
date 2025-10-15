from typing import List
from urllib.parse import urlparse
from ump.core.models.link import Link
from ump.core.settings import app_settings


def rewrite_links_to_local(process_id: str, links: List[Link]) -> List[Link]:
    """
    Replace remote links with local links when configured to do so.
    - Keep links pointing to local hosts unchanged.
    - For external links, replace href with a local API route to the process.

    Example: external href -> /processes/{process_id}/... or a link to the process detail.
    """
    if not app_settings.UMP_REWRITE_REMOTE_LINKS:
        return links

    rewritten: List[Link] = []
    for link in links:
        try:
            parsed = urlparse(link.href)
            # If link is already relative or points to localhost, leave as-is
            if not parsed.netloc or parsed.netloc in ("localhost", "127.0.0.1"):
                rewritten.append(link)
                continue
        except Exception:
            # If parsing fails, keep original
            rewritten.append(link)
            continue

        # Replace external link with a local reference to the process
        new_href = f"{app_settings.UMP_API_SERVER_URL_PREFIX.rstrip('/')}/processes/{process_id}"
        rewritten.append(Link(**{**link.model_dump(), "href": new_href}))

    return rewritten
