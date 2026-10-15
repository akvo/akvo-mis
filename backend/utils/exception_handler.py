from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    # DRF 3.15 started passing Http404's message through, which names
    # the model ("No FormData matches the given query."). Keep the
    # generic "Not found." clients have always received.
    if isinstance(exc, Http404):
        exc = NotFound()
    return drf_exception_handler(exc, context)
