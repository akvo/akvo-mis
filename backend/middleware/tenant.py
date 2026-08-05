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

# Infrastructure reaches the pod directly — a kubelet probe connects to the
# pod IP, so the request carries `Host: <pod-ip>:8000`, which names no
# workspace. The 404 that is right for a typo'd subdomain is wrong here: it
# fails the readiness probe, which holds the rollout, so setting
# BASE_DOMAIN would make every deploy time out. Cluster DNS and
# `kubectl port-forward` arrive the same way.
#
# This is one path, not the start of an exemption list. The distinction the
# class docstring draws — public *API* endpoints are exempted by being
# anonymous, never by being listed — still holds. Liveness is not an API
# endpoint; it answers "is this process up", it has no tenant by
# construction, and it will not grow siblings.
HEALTH_CHECK_PATH = "/api/v1/health/check"


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
        if request.path.startswith(HEALTH_CHECK_PATH):
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
