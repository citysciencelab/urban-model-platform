from ump.core.interfaces.site_info import SiteInfoPort
from ump.core.settings import app_settings

class StaticSiteInfoAdapter(SiteInfoPort):
    def get_site_info(self):
        base = app_settings.UMP_API_SERVER_URL_PREFIX.rstrip("/") or ""
        return {
            "title": app_settings.UMP_SITE_TITLE,
            "description": app_settings.UMP_SITE_DESCRIPTION,
            "contact": app_settings.UMP_SITE_CONTACT,
            "routes": [
                {"path": f"{base}/processes", "description": "List available processes"},
            ],
        }
