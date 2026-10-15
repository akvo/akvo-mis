import json

from django.test import SimpleTestCase
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


class RequestBodyLimitTest(SimpleTestCase):
    # Since DRF 3.17.2 JSON bodies go through HttpRequest.body, which
    # enforces DATA_UPLOAD_MAX_MEMORY_SIZE (Django default 2.5 MiB).
    # nginx admits up to 50M, so a large form save must still parse.

    def test_a_3_mib_json_body_parses(self):
        payload = {"blob": "x" * (3 * 1024 * 1024)}
        django_request = APIRequestFactory().post(
            "/", json.dumps(payload), content_type="application/json"
        )
        request = Request(django_request, parsers=[JSONParser()])
        self.assertEqual(request.data, payload)
