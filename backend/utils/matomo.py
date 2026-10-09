import logging
from typing import Any, Dict, Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def is_matomo_enabled() -> bool:
    """Check whether Matomo tracking is configured and active."""
    site_id = getattr(settings, "MATOMO_SITE_ID", None)
    url = getattr(settings, "MATOMO_URL", "")
    return bool(site_id and url)


def get_matomo_endpoint() -> str:
    """Return the Matomo tracking API endpoint URL."""
    base_url = getattr(settings, "MATOMO_URL", "").rstrip("/")
    return f"{base_url}/matomo.php"


def track_matomo_event(
    category: str,
    action: str,
    name: Optional[str] = None,
    value: Optional[float] = None,
    url: Optional[str] = None,
    user_id: Optional[str] = None,
    custom_dimensions: Optional[Dict[int, str]] = None,
    timeout: int = 3,
) -> bool:
    """
    Send an event tracking request to Matomo HTTP Tracking API.

    Returns True if request was sent successfully, False if disabled or failed.
    Never raises exceptions.
    """
    if not is_matomo_enabled():
        return False

    params: Dict[str, Any] = {
        "idsite": settings.MATOMO_SITE_ID,
        "rec": 1,
        "apiv": 1,
        "send_image": 0,
        "e_c": str(category)[:255],
        "e_a": str(action)[:255],
    }

    if name:
        params["e_n"] = str(name)[:255]
    if value is not None:
        params["e_v"] = value
    if url:
        params["url"] = url
    if user_id:
        params["uid"] = str(user_id)

    auth_token = getattr(settings, "MATOMO_AUTH_TOKEN", None)
    if auth_token:
        params["token_auth"] = auth_token

    if custom_dimensions:
        for dim_id, dim_val in custom_dimensions.items():
            if dim_id and dim_val:
                params[f"dimension{dim_id}"] = str(dim_val)[:255]

    try:
        response = requests.post(
            get_matomo_endpoint(),
            params=params,
            timeout=timeout,
        )
        return response.status_code < 400
    except Exception as exc:
        logger.warning("Matomo tracking request failed: %s", exc)
        return False


def track_matomo_page_view(
    url: str,
    action_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    subdomain: Optional[str] = None,
    user_id: Optional[str] = None,
    custom_dimensions: Optional[Dict[int, str]] = None,
    timeout: int = 3,
) -> bool:
    """
    Send a pageview tracking request to Matomo HTTP Tracking API.
    """
    if not is_matomo_enabled():
        return False

    dimensions = dict(custom_dimensions or {})
    dim_tenant = getattr(settings, "MATOMO_DIM_TENANT", None)
    if dim_tenant and tenant_name and dim_tenant not in dimensions:
        dimensions[dim_tenant] = str(tenant_name)[:255]

    dim_subdomain = getattr(settings, "MATOMO_DIM_SUBDOMAIN", None)
    if dim_subdomain and subdomain and dim_subdomain not in dimensions:
        dimensions[dim_subdomain] = str(subdomain)[:255]

    params: Dict[str, Any] = {
        "idsite": settings.MATOMO_SITE_ID,
        "rec": 1,
        "apiv": 1,
        "send_image": 0,
        "url": url,
    }

    if action_name:
        params["action_name"] = str(action_name)[:255]
    if user_id:
        params["uid"] = str(user_id)

    auth_token = getattr(settings, "MATOMO_AUTH_TOKEN", None)
    if auth_token:
        params["token_auth"] = auth_token

    for dim_id, dim_val in dimensions.items():
        if dim_id and dim_val:
            params[f"dimension{dim_id}"] = str(dim_val)[:255]

    try:
        response = requests.post(
            get_matomo_endpoint(),
            params=params,
            timeout=timeout,
        )
        return response.status_code < 400
    except Exception as exc:
        logger.warning("Matomo tracking request failed: %s", exc)
        return False


def track_submission_task(
    tenant_name: Optional[str] = None,
    form_name: Optional[str] = None,
    form_id: Optional[int] = None,
    source: str = "mobile",
    user_id: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> bool:
    """
    Background worker task or direct helper to track a form submission.
    Can be dispatched via Django-Q:
        async_task('utils.matomo.track_submission_task', ...)
    """
    if not is_matomo_enabled():
        return False

    action = "Mobile Sync" if source == "mobile" else "Webform Submit"
    custom_dimensions: Dict[int, str] = {}

    dim_tenant = getattr(settings, "MATOMO_DIM_TENANT", None)
    if dim_tenant and tenant_name:
        custom_dimensions[dim_tenant] = tenant_name

    dim_subdomain = getattr(settings, "MATOMO_DIM_SUBDOMAIN", None)
    if dim_subdomain and subdomain:
        custom_dimensions[dim_subdomain] = subdomain

    return track_matomo_event(
        category="Data Submission",
        action=action,
        name=form_name,
        user_id=user_id,
        custom_dimensions=custom_dimensions,
    )
