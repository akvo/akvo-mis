# =========================================================
# The embed document: author markup on an origin of its own (VIZ-019)
# =========================================================
# An embedded dashboard's snippet cannot run in this application's
# origin: that is cross-site scripting against every visitor of a public
# page, and `AUTH_TOKEN` is a cookie without HttpOnly, so a snippet could
# simply read the session out of `document.cookie`.
#
# It cannot run in an *opaque* origin either, which is what an earlier
# version of this feature tried. A `srcdoc` frame sandboxed without
# `allow-same-origin` reports `window.origin === "null"`, and measured
# against the two vendors this feature exists for, both fail there:
# Tableau's API sends `Origin: null` and CORS refuses it ("Failed to
# fetch"), and Power BI's own frame, which inherits the sandbox, cannot
# reach its storage ("This content isn't available").
#
# So the snippet is served as a document from a host that is not ours.
# The frame showing it may then carry `allow-same-origin`, because the
# origin that grants is the embed host's and never this application's.
#
# The embed host holds no session: `AUTH_TOKEN` is host-only, so the
# browser never sends it here. That is the isolation working, and it
# means this view cannot authorise anyone. It does not need to. The URL
# is minted by an endpoint that has already decided the caller may see
# the dashboard, and the signature is the proof of that decision
# travelling with the request.

from django.conf import settings
from django.core import signing
from django.core.cache import caches
from django.http import Http404, HttpResponse
from django.utils.crypto import get_random_string
from django.views.decorators.clickjacking import xframe_options_exempt

from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_host import is_embed_host, tenant_may_embed

SALT = "v1_visualization.embed"
# An hour. The token is proof of an authorisation decision taken when it
# was minted, so its lifetime is how long a revoked viewer could still
# load the frame. Short enough to bound that, long enough that a
# dashboard left open over a meeting does not break.
MAX_AGE = 60 * 60
# Preview carries unsaved markup, so it lives in the cache rather than in
# the token — a snippet can be 20k characters and a URL cannot.
PREVIEW_MAX_AGE = 60 * 15
# Its own cache alias, not `default`: that one is cleared in full whenever
# a form changes, which would take a pending preview with it.
PREVIEW_CACHE = "embed"


def _absolute(token):
    origin = (settings.EMBED_HOST or "").rstrip("/")
    if not origin:
        # Unconfigured: no URL at all, so the viewer can say "embedding is
        # not configured" instead of quietly rendering the markup here.
        return None
    return "{0}/api/v1/embed/{1}".format(origin, token)


def embed_url_for(dashboard):
    """Absolute URL of a published dashboard's embed document, or None.

    None for a workspace that is not entitled, exactly as for one on a
    deployment with no embed host: the viewer shows the same notice
    either way, and a reader is not told which of the two it is.
    """
    if dashboard.kind != DashboardKind.embed:
        return None
    if not tenant_may_embed(dashboard.tenant):
        return None
    return _absolute(signing.dumps({"d": dashboard.id}, salt=SALT))


def preview_url_for(snippet, tenant):
    """Absolute URL for unsaved markup, or None when it may not render.

    Preview has to show what the viewer will see (spec D-9) — it is the
    only warning an author gets that an embed is broken, since a
    cross-origin frame reports nothing back to us.

    The tenant travels inside the signed token rather than beside the
    snippet in the cache, because the token is what arrives at the embed
    host: that host resolves no tenant of its own (it is nobody's
    subdomain), so anything it needs to know about the workspace has to
    be carried to it. Signed, so a caller cannot name a workspace other
    than their own.
    """
    if not tenant_may_embed(tenant):
        return None
    key = "embed-preview:" + get_random_string(40)
    caches[PREVIEW_CACHE].set(key, snippet, PREVIEW_MAX_AGE)
    return _absolute(signing.dumps({"p": key, "t": tenant.id}, salt=SALT))


def _on_embed_host(request):
    """Is this request actually arriving on the embed host?

    The load-bearing check of this module. Without it the same URL could
    be framed on the application's own origin, which would run the
    snippet exactly where none of this is allowed to.
    """
    return is_embed_host(request.get_host())


def _snippet_from(payload):
    """The markup a valid token names, or None.

    Entitlement is re-checked here, and that is the point of gating at
    serve time rather than only where the URL is minted. A token is
    proof of a decision taken up to an hour ago; a workspace whose
    embedding has been revoked since must stop rendering everywhere,
    including in a tab that was opened while it still had it.
    """
    key = payload.get("p")
    if key:
        tenant = Tenant.objects.filter(pk=payload.get("t")).first()
        if not tenant_may_embed(tenant):
            return None
        return caches[PREVIEW_CACHE].get(key)

    dashboard = Dashboard.objects.filter(
        pk=payload.get("d"),
        kind=DashboardKind.embed,
        # Re-checked at serve time, not merely at mint time: unpublishing
        # should stop the frame loading rather than wait out the token.
        status=DashboardStatus.published,
    ).select_related("tenant").first()
    if dashboard is None or not tenant_may_embed(dashboard.tenant):
        return None
    # From the snapshot, never the live row (spec D-5): editing a
    # published embed must not change what viewers see until it is
    # published again.
    return (dashboard.published_config or {}).get("embed_snippet")


# The author's markup goes in verbatim. Centred here rather than in the
# framing page because layout inside a cross-origin frame is not ours to
# reach — this document is the only place that can put a vendor's
# fixed-width report in the middle of the space it was given.
#
# `safe center` rather than plain `center`, and the word is load-bearing.
# A centred flex item wider than its container overflows equally on both
# sides, and the left overflow is unreachable: no scroll position reaches
# it, so the report is simply cut off. Measured at a 600px frame around
# an 800px report, plain centring puts its left edge at -100px; `safe`
# falls back to flex-start and puts it at 0, where the whole of it can be
# scrolled to. Browsers too old to know the keyword drop the declaration
# and get flex-start, which is the same fallback.
#
# `align-items: flex-start` avoids the identical trap vertically: a tall
# report centred in a short frame would lose its top edge the same way.
#
# The last rule sizes a frame the author left unsized. A bare
# `<iframe src="...">` has no intrinsic size, so it renders at the HTML
# default of 300x150 — a postage stamp in the middle of a full-page
# frame, which is what issue #378 reported. There is nowhere else to fix
# it: the framing page cannot reach inside a cross-origin document, so
# this stylesheet is the only thing that can give that frame a size.
#
# The two `:not()` guards are the whole design, and removing them breaks
# every vendor snippet. A stylesheet rule outranks the `width` and
# `height` *attributes* that Power BI and friends emit, so a bare
# `iframe{width:100%}` would silently override an authored 600x373.5 and
# distort the report. Matching only a frame that declares neither leaves
# every sized snippet exactly as it was. Inline `style` needs no guard:
# it already beats a stylesheet, so an author who sizes that way keeps
# their size for free.
#
# Only `body>iframe`, deliberately, and not any unsized top-level
# element: Tableau ships a `<div>` that its own script measures and
# sizes, and stretching that would fight the vendor rather than help it.
DOCUMENT = (
    '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
    '<meta name="robots" content="noindex">'
    "<style>html,body{height:100%}"
    "body{margin:0;display:flex;justify-content:safe center;"
    "align-items:flex-start;overflow:auto;background:#fff}"
    "body>iframe:not([width]):not([height]){width:100%;height:100%}"
    "</style>"
    "</head><body>"
)


@xframe_options_exempt
def serve_embed(request, version, token):
    """Serve one embedded dashboard's markup as its own document.

    `xframe_options_exempt` because XFrameOptionsMiddleware would
    otherwise send SAMEORIGIN and the browser would refuse to frame the
    very document this view exists to be framed.
    """
    if not _on_embed_host(request):
        raise Http404("not the embed host")
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        # Covers expiry too (SignatureExpired subclasses it). One answer
        # for forged, tampered and stale alike: the caller learns nothing
        # from the difference.
        raise Http404("bad embed token")

    snippet = _snippet_from(payload)
    if not snippet:
        raise Http404("nothing to embed")

    response = HttpResponse(
        DOCUMENT + snippet + "</body></html>", content_type="text/html"
    )
    # A private dashboard's markup must not sit in a shared cache, and
    # nothing here is worth caching anyway — the token changes each time.
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
