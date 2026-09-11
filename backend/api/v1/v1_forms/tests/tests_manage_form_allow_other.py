from django.test import TestCase

from api.v1.v1_forms.views import (
    _normalize_editor_payload,
    _to_editor_format,
)


def _payload(**question):
    return {
        "question_group": [
            {
                "id": 1,
                "name": "g",
                "question": [
                    {"id": 10, "type": "option", "label": "Gender", **question}
                ],
            }
        ]
    }


def _question(data):
    return data["question_group"][0]["question"][0]


class AllowOtherEditorMappingTestCase(TestCase):
    """The editor keeps allowOther/allowOtherText at the question top level;
    the backend stores them in Questions.extra, which is what the web form
    reads. The two editor conversion helpers must translate both ways."""

    def test_normalize_folds_allow_other_into_extra(self):
        q = _question(
            _normalize_editor_payload(
                _payload(allowOther=True, allowOtherText="Specify")
            )
        )
        self.assertNotIn("allowOther", q)
        self.assertNotIn("allowOtherText", q)
        self.assertEqual(
            q["extra"], {"allowOther": True, "allowOtherText": "Specify"}
        )

    def test_normalize_keeps_existing_extra_keys(self):
        q = _question(
            _normalize_editor_payload(
                _payload(allowOther=True, extra={"type": "administration"})
            )
        )
        self.assertEqual(
            q["extra"], {"type": "administration", "allowOther": True}
        )

    def test_normalize_unchecked_allow_other_clears_extra(self):
        q = _question(
            _normalize_editor_payload(
                _payload(
                    allowOther=False,
                    allowOtherText="",
                    extra={"allowOther": True, "allowOtherText": "x"},
                )
            )
        )
        self.assertIsNone(q["extra"])

    def test_normalize_without_allow_other_leaves_extra_untouched(self):
        q = _question(_normalize_editor_payload(_payload(extra=None)))
        self.assertIsNone(q["extra"])

    def test_to_editor_format_lifts_allow_other_from_extra(self):
        q = _question(
            _to_editor_format(
                _payload(
                    extra={
                        "type": "administration",
                        "allowOther": True,
                        "allowOtherText": "Specify",
                    }
                )
            )
        )
        self.assertTrue(q["allowOther"])
        self.assertEqual(q["allowOtherText"], "Specify")
        self.assertEqual(q["extra"], {"type": "administration"})

    def test_to_editor_format_drops_empty_extra(self):
        q = _question(_to_editor_format(_payload(extra={"allowOther": True})))
        self.assertTrue(q["allowOther"])
        self.assertNotIn("extra", q)

    def test_round_trip_is_stable(self):
        editor_in = _payload(allowOther=True, allowOtherText="Specify")
        backend = _normalize_editor_payload(editor_in)
        editor_out = _to_editor_format(backend)
        self.assertEqual(_question(editor_out), _question(editor_in))
