"""Which tenant is this request for, according to its URL?

The single seam for host-based tenant routing. Today a tenant lives at
one subdomain of BASE_DOMAIN; a custom-domain tier would add a branch
here and nowhere else, which is the whole reason host parsing is
confined to this module.

With BASE_DOMAIN unset — the default, and what the test suite and any
single-host deployment run with — every host is the base domain and no
host resolves to a tenant, so host routing is inert.
"""
from urllib.parse import urlparse

from django.conf import settings

from api.v1.v1_users.models import Tenant


def _normalize(host):
    """Strip the port and case so `ACME.app.com:3000` compares equal."""
    if not host:
        return ""
    return host.split(":")[0].strip().lower()


def is_base_domain(host):
    """Is this the bare base domain — the tenant-less signup context?

    Distinguishing this from "some other host" is what lets the caller
    treat an unresolved host as a missing workspace rather than as the
    signup page. `www.` is accepted because it is the same site.
    """
    if not settings.BASE_DOMAIN:
        return True
    base = settings.BASE_DOMAIN.lower()
    return _normalize(host) in (base, f"www.{base}")


def resolve_tenant_from_host(host):
    """The tenant this host belongs to, or None if it belongs to none."""
    if not settings.BASE_DOMAIN or is_base_domain(host):
        return None
    host = _normalize(host)
    suffix = f".{settings.BASE_DOMAIN.lower()}"
    if not host.endswith(suffix):
        return None
    label = host[: -len(suffix)]
    # Exactly one label. Allowing dots would make `acme.staging.app.com`
    # resolve to nothing useful, or worse, to a tenant it is not.
    if not label or "." in label:
        return None
    return Tenant.objects.filter(subdomain=label).first()


def tenant_web_url(tenant):
    """Where this workspace's app lives — for links we send by email.

    An activation link has to land on the workspace's own host, because
    everything after it (the configuration form, then the app) is
    enforced to that host. Sending it to the base domain would strand
    the registrant one click from a login they cannot use.

    `WEBDOMAIN` keeps supplying the scheme and port — which differ
    between local development and production — while `BASE_DOMAIN`
    supplies the host. With no base domain or no tenant there is only
    one address, and it is `WEBDOMAIN` unchanged.
    """
    if not settings.BASE_DOMAIN or not tenant:
        return settings.WEBDOMAIN
    parsed = urlparse(settings.WEBDOMAIN)
    port = f":{parsed.port}" if parsed.port else ""
    return (
        f"{parsed.scheme or 'https'}://"
        f"{tenant.subdomain}.{settings.BASE_DOMAIN}{port}"
    )
