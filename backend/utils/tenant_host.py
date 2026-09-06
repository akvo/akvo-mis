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


def embed_hostname():
    """Hostname of the origin that serves embedded content, or "".

    `EMBED_HOST` is configured as a full origin because that is what the
    frontend needs; everything host-shaped derives from here so the two
    readings cannot drift. Empty means embedding is unconfigured, and
    every caller treats that as "off" rather than "anything goes".
    """
    return (urlparse(settings.EMBED_HOST or "").hostname or "").lower()


def is_embed_host(host):
    """Does this host serve embedded content rather than the app?"""
    configured = embed_hostname()
    return bool(configured) and _normalize(host) == configured


def resolve_tenant_from_host(host):
    """The tenant this host belongs to, or None if it belongs to none."""
    if is_base_domain(host):
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
        f"{parsed.scheme}://{tenant.subdomain}.{settings.BASE_DOMAIN}{port}"
    )


def public_tenant(request):
    """The workspace an anonymous reader is looking at.

    `None` means serve nothing — an empty queryset, never a filter on
    `tenant IS NULL`. The two are not the same: tenant-less rows exist
    in the test suite and in any database predating the MT-002
    backfill, and filtering on NULL would quietly serve those to
    anonymous callers on the base domain.

    With BASE_DOMAIN set the host names the workspace or nothing does.
    With it unset — mohhs, unicef-fsm, the test suite — no host can,
    but the deployment IS one workspace, so the sole Tenant row is it.
    Two or more rows means a dev or test database that no host can
    disambiguate: an anonymous reader seeing an empty menu is a bug
    report, one seeing another tenant's dashboard is an incident.
    """
    if settings.BASE_DOMAIN:
        return getattr(request, "tenant", None)
    tenants = list(Tenant.objects.all()[:2])
    return tenants[0] if len(tenants) == 1 else None
