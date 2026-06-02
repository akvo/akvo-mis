# Implementation Plan: Form Builder Backend API (FB-002)

**Asana task**: FB-002
**Followed by**: FB-003 (form-builder-integration frontend)
**Status**: ✅ Implemented

---

## Prerequisites

- [x] Backend services running: `./dc.sh up -d`
- [x] Confirmed `akvo-react-form-editor` emits `"image"` — canonical type name used throughout

---

## Task Breakdown

---

### Group A: Constants ✅

**File**: `backend/api/v1/v1_forms/constants.py`

`QuestionTypes.image = 8` was already renamed before this sprint. `FormStatus` was added after `FormTypes`:

```python
class FormStatus:
    draft = 1
    published = 2

    FieldStr = {
        draft: "draft",
        published: "published",
    }
```

Note: `FieldStr` values are lowercase strings (not capitalized). This is consistent with how `status` is serialized in API responses.

---

### Group B: Model Changes ✅

**File**: `backend/api/v1/v1_forms/models.py`

Added three fields to `Forms`:

```python
from api.v1.v1_forms.constants import QuestionTypes, AttributeTypes, FormTypes, FormStatus

class Forms(models.Model):
    # ... existing fields ...
    status = models.IntegerField(
        choices=FormStatus.FieldStr.items(),
        default=FormStatus.draft,
    )
    published_at = models.DateTimeField(null=True, blank=True, default=None)
    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="next_versions",
        null=True,
        blank=True,
    )
```

---

### Group C: Migration ✅

**File**: `backend/api/v1/v1_forms/migrations/0008_add_form_status_and_version.py`

Generated via:
```bash
./dc.sh exec backend python manage.py makemigrations v1_forms --name add_form_status_and_version
```

Manually edited to set `default=2` (PUBLISHED) for `status` on the `AddField` + `preserve_default=False` so existing forms are live:

```python
migrations.AddField(
    model_name='forms',
    name='status',
    field=models.IntegerField(
        choices=[(1, 'draft'), (2, 'published')],
        default=2,  # PUBLISHED for existing rows
    ),
    preserve_default=False,
),
```

---

### Group D: Serializers ✅

**File**: `backend/api/v1/v1_forms/serializers.py`

No `FormCreateSerializer` or sub-serializer pattern — validation and mutation are handled by `functions.py` (see Group E). Serializers are read-only response shapes.

#### `ListFormSerializer` — extended with `status`

```python
class ListFormSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return FormStatus.FieldStr.get(obj.status, "draft")

    class Meta:
        model = Forms
        fields = ["id", "name", "version", "status", "parent"]
```

#### `FormDetailQuestionSerializer` — question with `disable_delete`

Returns question data with all fields needed by the editor. `disable_delete` is `True` when answers exist, `None` otherwise (following `akvo-form-service` pattern):

```python
class FormDetailQuestionSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    option = serializers.SerializerMethodField()
    disable_delete = serializers.SerializerMethodField()

    def get_type(self, obj):
        return QuestionTypes.FieldStr.get(obj.type, "").lower()

    def get_disable_delete(self, obj):
        from api.v1.v1_data.models import Answers
        if Answers.objects.filter(question=obj).exists():
            return True
        return None

    class Meta:
        model = Questions
        fields = [
            "id", "order", "name", "label", "short_label", "type",
            "meta", "required", "rule", "dependency", "dependency_rule",
            "api", "extra", "tooltip", "fn", "pre", "display_only",
            "option", "disable_delete",
        ]
```

#### `FormDetailQuestionGroupSerializer`

```python
class FormDetailQuestionGroupSerializer(serializers.ModelSerializer):
    question = FormDetailQuestionSerializer(
        source="question_group_question", many=True
    )

    class Meta:
        model = QuestionGroup
        fields = ["id", "name", "label", "order", "repeatable", "repeat_text", "question"]
```

#### `FormDetailSerializer`

Standalone serializer (does not extend `FormDataSerializer`):

```python
class FormDetailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    question_group = FormDetailQuestionGroupSerializer(
        source="form_question_group", many=True
    )

    def get_status(self, obj):
        return FormStatus.FieldStr.get(obj.status, "draft")

    class Meta:
        model = Forms
        fields = [
            "id", "name", "version", "status", "published_at",
            "type", "approval_instructions", "parent", "question_group",
        ]
```

#### `FormVersionSerializer`

```python
class FormVersionSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return FormStatus.FieldStr.get(obj.status, "draft")

    class Meta:
        model = Forms
        fields = ["id", "version", "status", "published_at", "name"]
```

---

### Group E: Helper Functions ✅

**File**: `backend/api/v1/v1_forms/functions.py` (new file)

Plain helper functions — no DRF serializer wrappers. Permission check moved to `IsFormBuilder` in `custom_permissions.py` (see Group F).

| Function | Signature | Purpose |
|---|---|---|
| `_type_str_to_int(type_str)` | `str → int\|None` | `getattr(QuestionTypes, type_str.lower(), None)` |
| `_form_type_str_to_int(type_str)` | `str → int` | `"registration"\|"monitoring"` → int |
| `_generate_unique_name(base, existing_names)` | `str, set → str` | slugify + `_1`, `_2` suffix until unique |
| `_save_questions(group, questions_data, question_names)` | — | Create/update questions for a group; protect answered questions |
| `save_form(data, instance=None)` | `dict, Forms? → Forms` | `@transaction.atomic` — create or fully replace a DRAFT |
| `version_on_edit(original_form, data)` | `Forms, dict → Forms` | `@transaction.atomic` — new DRAFT with `version+1`, `previous_version=original` |
| `duplicate_form(original_form)` | `Forms → Forms` | `@transaction.atomic` — deep copy as new DRAFT |
| `validate_form_payload(data)` | `dict → list[str]` | Return list of errors; empty if valid |

**`IsFormBuilder` permission class** (`backend/utils/custom_permissions.py`):

```python
class IsFormBuilder(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_superuser:
            return request.user.user_user_role.filter(
                role__role_role_feature_access__type=FeatureTypes.form_builder,
                role__role_role_feature_access__access=FeatureAccessTypes.form_builder,
            ).exists()
        return request.user.is_superuser
```

Consistent with `AddUserAccess`, `IsEditor`, `IsApprover` pattern in the same file.

---

### Group F: View Functions ✅

**File**: `backend/api/v1/v1_forms/views.py`

All CRUD views use `@permission_classes([IsAuthenticated, IsFormBuilder])`. No inline permission checks (except DELETE which adds a tighter superuser gate). OpenAPI docs via `@extend_schema(tags=["Form Builder"])`.

#### `list_form` (extended to handle POST)

```python
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def list_form(request, version):
    if request.method == "POST":
        return _handle_create_form(request)
    instance = Forms.objects.filter(parent__isnull=True).all()
    return Response(ListFormSerializer(instance=instance, many=True).data)
```

#### `_handle_create_form` (plain helper, NOT `@api_view`)

Calling another `@api_view`-decorated function from within one causes a DRF `AssertionError` (`request must be HttpRequest`). The solution is a plain helper:

```python
def _handle_create_form(request):
    if not IsFormBuilder().has_permission(request, None):
        return Response({"message": "Permission denied"}, status=403)
    errors = validate_form_payload(request.data)
    if errors:
        return Response({"message": errors[0]}, status=400)
    parent_id = request.data.get("parent")
    if request.data.get("type") == "monitoring" and parent_id:
        try:
            parent = Forms.objects.get(id=parent_id)
        except Forms.DoesNotExist:
            return Response({"parent": "Parent form not found"}, status=400)
        if parent.status != FormStatus.published or parent.type != FormTypes.registration:
            return Response(
                {"parent": "Parent must be a published registration form"}, status=400
            )
    try:
        form = save_form(request.data)
    except ValueError as exc:
        parts = str(exc).split("|", 1)
        return Response({"message": parts[0], "details": parts[1] if len(parts) > 1 else ""}, status=400)
    return Response(FormDetailSerializer(instance=form).data, status=201)
```

#### `form_detail` (`GET` / `PUT` / `DELETE`)

```python
@extend_schema(tags=["Form Builder"], summary="Get, update or delete a form")
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def form_detail(request, version, pk):
    ...
    if request.method == "PUT":
        if form.status == FormStatus.published:
            new_form = version_on_edit(form, request.data)
            return Response(FormDetailSerializer(instance=new_form).data, status=201)
        updated = save_form(request.data, instance=form)
        return Response(FormDetailSerializer(instance=updated).data)

    if request.method == "DELETE":
        if not request.user.is_superuser:  # tighter gate: superuser only
            return Response({"message": "Permission denied"}, status=403)
        if FormData.objects.filter(form=form).exists():
            return Response({"message": "Cannot delete form with existing submissions"}, status=409)
        form.delete()
        return Response(status=204)
```

#### Other views

```python
@extend_schema(tags=["Form Builder"], summary="Publish a draft form")
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def publish_form(request, version, pk): ...

@extend_schema(tags=["Form Builder"], summary="Duplicate a form as a new draft")
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def duplicate_form_view(request, version, pk): ...  # named _view to avoid clash with imported duplicate_form

@extend_schema(tags=["Form Builder"], summary="List version chain for a form")
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def form_versions(request, version, pk): ...
```

---

### Group G: URL Registration ✅

**File**: `backend/api/v1/v1_forms/urls.py`

```python
from api.v1.v1_forms.views import (
    web_form_details, list_form, form_data, check_form_approver, form_approver,
    form_detail, publish_form, duplicate_form_view, form_versions,
)

urlpatterns = [
    # Existing read-only (unchanged)
    re_path(r"^(?P<version>(v1))/form/web/(?P<form_id>[0-9]+)", web_form_details),
    re_path(r"^(?P<version>(v1))/form/(?P<form_id>[0-9]+)", form_data),
    re_path(r"^(?P<version>(v1))/form/approver", form_approver),
    re_path(r"^(?P<version>(v1))/form/check-approver/(?P<form_id>[0-9]+)", check_form_approver),

    # CRUD: sub-resource routes first (more specific before generic)
    re_path(r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/publish$", publish_form),
    re_path(r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/duplicate$", duplicate_form_view),
    re_path(r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/versions$", form_versions),
    re_path(r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)$", form_detail),
    re_path(r"^(?P<version>(v1))/forms$", list_form),
]
```

Note: `POST /api/v1/forms` and `GET /api/v1/forms` share the same `list_form` view, which dispatches by method internally. There is no separate `create_form` URL entry.

All new views receive a `version` kwarg from the URL regex — view signatures are `def view_name(request, version, pk)`.

---

### Group H: Extend `list_form` ✅

`list_form` handles both `GET` and `POST`. The POST branch delegates to `_handle_create_form(request)` — a plain (non-DRF-decorated) helper. This avoids the DRF double-wrap issue where calling one `@api_view` function from another causes an `AssertionError`.

---

## Testing Requirements ✅

**File**: `backend/api/v1/v1_forms/tests/tests_form_crud.py` (note: `tests_` prefix, not `test_`)

`FormCRUDTestCase(TestCase)` with `@override_settings(USE_TZ=False, TEST_ENV=True)`.

setUp calls management commands then resets PostgreSQL sequences to avoid PK conflicts with seeded explicit IDs:

```python
with connection.cursor() as cur:
    for tbl in ["form", "question_group", "question", "option"]:
        cur.execute(
            f"SELECT setval("
            f"pg_get_serial_sequence('{tbl}', 'id'),"
            f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
            f"false)"
        )
```

| Test | Status |
|---|---|
| `test_create_draft_form` | ✅ |
| `test_create_requires_form_builder` | ✅ |
| `test_update_draft_form` | ✅ |
| `test_update_published_creates_new_version` | ✅ |
| `test_version_chain_correct` | ✅ |
| `test_publish_form` | ✅ |
| `test_publish_already_published` | ✅ |
| `test_duplicate_form` | ✅ |
| `test_delete_form_with_submissions` | ✅ |
| `test_delete_form_without_submissions` | ✅ |
| `test_delete_requires_superuser` | ✅ |
| `test_get_form_includes_status` | ✅ |
| `test_list_forms_includes_status` | ✅ |
| `test_image_type_canonical` | ✅ |
| `test_name_autogenerated_if_missing` | ✅ |
| `test_update_cannot_delete_group_with_answers` | ✅ |
| `test_update_cannot_delete_question_with_answers` | ✅ |
| `test_disable_delete_in_response` | ✅ |
| `test_get_form_detail` | ✅ |
| `test_get_form_not_found` | ✅ |
| `test_update_draft_form_replaces_in_place` | ✅ |
| `test_create_monitoring_form_requires_published_parent` | ⬜ not yet written |
| `test_create_monitoring_form_requires_registration_parent` | ⬜ not yet written |
| `test_name_uniqueness_enforced` | ⬜ not yet written |
| `test_update_cannot_change_question_type_with_answers` | ⬜ not yet written |

Run:
```bash
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests.tests_form_crud
```

---

## Handoff Notes for FB-003

After this spec is delivered, FB-003 frontend can start. Key contracts FB-003 depends on:

| Contract | Detail |
|---|---|
| `POST /api/v1/forms` → 201 | Response includes `{ id, status: "draft", version: 1, ... }` |
| `PUT /api/v1/forms/{id}` → 200 | Draft saved in-place; response includes `{ id, status: "draft", ... }` |
| `PUT /api/v1/forms/{id}` → 201 | Published form — response includes new `{ id, version: n+1, status: "draft" }` |
| `GET /api/v1/forms/{id}` | Includes `status`, `version`, `published_at`, `question_group` with `disable_delete` |
| `GET /api/v1/forms` | Items include `status` and `version` |
| `"image"` type | Only accepted string; stored as `QuestionTypes.image = 8` |
| Permission | `IsFormBuilder` class in `utils/custom_permissions.py`; `FeatureAccessTypes.form_builder` |
