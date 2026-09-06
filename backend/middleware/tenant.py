"""Bind every request to the workspace named by its host.

Two jobs, in order:

1. **Resolve.** `request.tenant` is the tenant the URL host belongs to,
   or `None` on the tenant-less base domain. Everything downstream that
   needs to know "which workspace is this page for" reads it from here
   rather than parsing hosts again.
2. **Enforce.** A session created for one workspace must not be usable on
   another's host. This is defence in depth: `for_user` still decides
   what data a query returns, and would keep doing so if this middleware
   were removed. What it adds is a boundary that fails closed at the
   edge, before any view has a chance to forget the scoping.

With `BASE_DOMAIN` unset the whole thing is inert — every host is the
base domain, nothing resolves, nothing is enforced — which is how the
test suite and any single-host deployment run.
"""

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

from utils.tenant_host import is_base_domain, resolve_tenant_from_host

# The two requests that must be answered on whatever host they arrive on.
#
# `health/check`: infrastructure reaches the pod directly — a kubelet probe
# connects to the pod IP, so the request carries `Host: <pod-ip>:8000`,
# which names no workspace. The 404 that is right for a typo'd subdomain is
# wrong here: it fails the readiness probe, which holds the rollout, so
# setting BASE_DOMAIN would make every deploy time out. Cluster DNS and
# `kubectl port-forward` arrive the same way.
#
# `config.js`: the bootstrap script `index.html` loads before any React
# code runs. What it carries — app name, base domain, role features — is
# deployment-wide, with nothing tenant-specific in it, so there is no
# workspace here to be wrong about. Refusing it does not produce a "no such
# workspace" page, it produces a blank one: the frontend reads
# `window.appConfig` at module load and throws without it, so the very page
# that would explain the 404 is the one the 404 prevents. Worse, the nginx
# cache in front of this path is keyed without the host, so one refusal —
# a probe, a typo'd subdomain — is then served to every host until it
# expires.
#
# Still not the start of an exemption list. The distinction the class
# docstring draws — public *API* endpoints are exempted by being anonymous,
# never by being listed — holds for both: neither is an API endpoint.
# Liveness answers "is this process up"; config.js is a static asset that
# happens to be served by Django. Both have no tenant by construction.
# `embed/`: the embedded-dashboard document (VIZ-019). It is served on
# EMBED_HOST, a host deliberately outside the workspace namespace, so
# `resolve_tenant_from_host` finds nothing and the 404 above would refuse
# every embed before its view ran. It belongs here for the same reason as
# the two above rather than as the start of a list: it is not an API
# endpoint but a document, and it has no tenant by construction — the
# authorisation happened when its signed URL was minted by an endpoint
# that did know the caller, and the signature is what travels with it.
EXEMPT_PATHS = (
    "/api/v1/health/check",
    "/api/v1/config.js",
    "/api/v1/embed/",
)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        host = request.get_host()
        request.tenant = resolve_tenant_from_host(host)

        # Resolved first, so a probe arriving on a real workspace host
        # still reports that tenant, then exempted from both the 404 and
        # enforcement below.
        if request.path.startswith(EXEMPT_PATHS):
            return self.get_response(request)

        # A host that is neither the signup domain nor a workspace names
        # nothing this deployment serves. Answering 404 before the view
        # runs also means a typo'd subdomain gets "no such workspace"
        # rather than a login page it could never log in to.
        if request.tenant is None and not is_base_domain(host):
            return JsonResponse({"message": "Workspace not found"}, status=404)

        # Enforcement needs an account to compare, so it is skipped for
        # anonymous requests — which is every public endpoint, including
        # ones added after this was written. That is deliberate: an
        # explicit exemption list would need editing by whoever adds the
        # next public path, and nothing would remind them.
        if request.tenant is not None:
            user = self._authenticated_user(request)
            if user is not None and user.tenant_id != request.tenant.id:
                return JsonResponse(
                    {
                        "message": "This account belongs to a different "
                        "workspace",
                        # We already know both sides of the mismatch, so
                        # naming the right address turns the frontend's
                        # dead end into a redirect. The session itself is
                        # valid — it is only in the wrong place — and
                        # subdomains are guessable anyway, so this
                        # discloses nothing the URL bar does not.
                        "subdomain": (
                            user.tenant.subdomain if user.tenant_id else ""
                        ),
                    },
                    status=403,
                )
        return self.get_response(request)

    def _authenticated_user(self, request):
        # JWT authentication happens at the view layer in this stack, so
        # request.user is still anonymous here and we have to run it
        # ourselves.
        try:
            result = self.jwt_auth.authenticate(request)
        except Exception:
            # A malformed, expired or revoked token is the view's 401 to
            # give. Only a session that is genuinely valid can be on the
            # wrong host, and only that deserves a 403.
            return None
        return result[0] if result else None
