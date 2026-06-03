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

**File**: `backend/api/v1/v1_forms/migrations/0007_forms_previous_version_forms_published_at_and_more.py`

Generated via:
```bash
./dc.sh exec backend python manage.py makemigrations v1_forms
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
        # import moved to module top (not inline — see feedback_backend_imports.md)
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
            "active_version_id",
            "type", "approval_instructions", "parent", "question_group",
        ]
```

#### `FormPublishedVersionSerializer`

Replaces the original `FormVersionSerializer` (which serialized `Forms` objects following `previous_version` FK chains — that chain is never populated after FB-002). This serializer targets `FormPublishedVersion` records:

```python
class FormPublishedVersionSerializer(serializers.ModelSerializer):
    published_by = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    def get_published_by(self, instance):
        return instance.published_by.email if instance.published_by else None

    def get_is_active(self, instance):
        return instance.form.active_version_id == instance.id

    class Meta:
        model = FormPublishedVersion
        fields = ["id", "version", "published_at", "published_by", "is_active"]
```

---

### Group E: Helper Functions ✅

**File**: `backend/api/v1/v1_forms/functions.py` (new file)

Plain helper functions — no DRF serializer wrappers. Permission check moved to `IsFormBuilder` in `custom_permissions.py` (see Group F).

| Function | Signature | Purpose |
|---|---|---|
| `_parse_form_type(type_val)` | `int\|str → int` | Accepts `1`/`2` or `"registration"`/`"monitoring"` |
| `_generate_unique_name(base, existing_names)` | `str, set → str` | slugify + `_1`, `_2` suffix until unique |
| `_save_questions(group, questions_data, question_names)` | — | Create/update questions for a group; uses `objects_with_deleted` to look up IDs so a soft-deleted question ID in the payload is restored rather than re-created; protect answered questions |
| `save_form(data, instance=None)` | `dict, Forms? → Forms` | `@transaction.atomic` — create or partially update a form in-place; on update, only mutates keys present in `data`; skips `question_group` unless key is present; does **not** increment `version` (version is managed by `create_published_version`) |
| `create_published_version(form, user)` | `Forms, user → FormPublishedVersion` | `@transaction.atomic` — builds snapshot, inserts `FormPublishedVersion`, syncs `form.version = next_version` and `form.active_version = pv`; only sets `status`/`published_at` on draft→published transition |
| `restore_from_snapshot(form, pv)` | `Forms, FormPublishedVersion → None` | `@transaction.atomic` — two-pass rollback: Pass 1 soft-deletes active rows absent from snapshot; Pass 2 restores snapshot rows via `objects_with_deleted` (clears `deleted_at`) and syncs all fields including options; sets `form.active_version = pv` |
| `duplicate_form(original_form)` | `Forms → Forms` | `@transaction.atomic` — deep copy as new DRAFT |
| `validate_form_payload(data, partial=False)` | `dict, bool → list[str]` | `partial=True` makes `name`/`type` optional; validates `type` as int or string if present |

**`_save_questions` null-safe defaults** (D-11):
- `dependency_rule`: `q_data.get("dependency_rule") or "AND"` — a present `null` would bypass the `"AND"` default with `get(..., "AND")`
- `display_only`: `q_data.get("display_only") or False` — same pattern

**`FormBuilderAccess` factory** (`backend/utils/custom_permissions.py`):

```python
def FormBuilderAccess(required_access):
    """Return a permission class for the given granular access type."""
    class _Permission(BasePermission):
        def has_permission(self, request, view):
            if request.user.is_superuser:
                return True
            return request.user.user_user_role.filter(
                role__role_role_feature_access__type=FeatureTypes.form_builder,
                role__role_role_feature_access__access=required_access,
            ).exists()
    return _Permission
```

---

### Group F: FormBuilderViewSet ✅

**Files**: `backend/api/v1/v1_forms/views.py`, `backend/api/v1/v1_forms/urls.py`

All form builder CRUD views are consolidated into a single `FormBuilderViewSet(ModelViewSet)`. See [D-10](../form-builder-backend-api/design.md) for the rationale.

#### `_normalize_editor_payload(data)` — module-level helper

Both `create` and `update` actions call this before validation to translate `akvo-react-form-editor` field names to backend conventions:

- `question_groups` → `question_group` (plural → singular)
- `questions` → `question` inside each group
- `options` → `option` inside each question
- `repeatText` → `repeat_text`
- `displayOnly` → `display_only`
- `photo` type → `image`
- `questionGroupId` key removed from question objects

Critically: if neither `question_group` nor `question_groups` is present in the input, the payload is returned untouched — name-only PUTs (`{"name": "..."}`) do not trigger group processing in `save_form`.

#### Old function → ViewSet action mapping

| Removed function | ViewSet action | Permission |
|---|---|---|
| `_handle_create_form` (POST) | `create` | `FormBuilderAccess(form_create)` |
| `form_detail GET` | `retrieve` | `FormBuilderAccess(form_view)` |
| `form_detail PUT` | `update` | `FormBuilderAccess(form_edit)` |
| `form_detail DELETE` | `destroy` | `IsSuperAdmin` |
| `publish_form` | `@action publish` | `FormBuilderAccess(form_publish)` |
| `duplicate_form_view` | `@action duplicate` | `FormBuilderAccess(form_create)` |
| `form_versions` | `@action versions` | `FormBuilderAccess(form_view)` + `FormBuilderAccess(form_edit)` |

`list_form` is retained as a standalone `@api_view(["GET"])` function for `GET /api/v1/forms` — flat list, no auth, backward compat for existing mobile/web clients.

The ViewSet handles all form builder CRUD at `GET|POST /api/v1/manage/forms` and sub-routes.

#### `get_permissions()` — all per-action gates in one place

```python
def get_permissions(self):
    perm_map = {
        "list":      [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_view)],
        "create":    [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_create)],
        "retrieve":  [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_view)],
        "update":    [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_edit)],
        "destroy":   [IsAuthenticated, IsSuperAdmin],
        "publish":   [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_publish)],
        "unpublish": [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_publish)],
        "duplicate": [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_create)],
        "versions":  [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_view),
                      FormBuilderAccess(FeatureAccessTypes.form_edit)],
        "activate":  [IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_publish)],
    }
    return [p() for p in perm_map.get(self.action, [IsAuthenticated])]
```

#### URL patterns (manual, no router)

```python
# Backward-compat flat list — no auth, no pagination
re_path(r"^(?P<version>(v1))/forms$", list_form),

# Form builder CRUD — /manage/forms prefix, pagination_class = Pagination
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/publish$",
    FormBuilderViewSet.as_view({"post": "publish"})),
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/duplicate$",
    FormBuilderViewSet.as_view({"post": "duplicate"})),
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/versions$",
    FormBuilderViewSet.as_view({"get": "versions"})),
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/unpublish$",
    FormBuilderViewSet.as_view({"post": "unpublish"})),
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/activate/(?P<version_id>[0-9]+)$",
    FormBuilderViewSet.as_view({"post": "activate"})),
re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)$",
    FormBuilderViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"})),
re_path(r"^(?P<version>(v1))/manage/forms$",
    FormBuilderViewSet.as_view({"get": "list", "post": "create"})),
```

---

### Group G: URL Registration ✅

**File**: `backend/api/v1/v1_forms/urls.py`

```python
from api.v1.v1_forms.views import (
    web_form_details, list_form, form_data, check_form_approver, form_approver,
    FormBuilderViewSet,
)

urlpatterns = [
    # Existing read-only (unchanged)
    re_path(r"^(?P<version>(v1))/forms$", list_form),
    re_path(r"^(?P<version>(v1))/form/(?P<form_id>[0-9]+)", form_data),
    re_path(r"^(?P<version>(v1))/form/web/(?P<form_id>[0-9]+)", web_form_details),
    re_path(r"^(?P<version>(v1))/form/approver", form_approver),
    re_path(r"^(?P<version>(v1))/form/check-approver/(?P<form_id>[0-9]+)", check_form_approver),

    # Manage Forms CRUD (sub-resource routes before generic)
    re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/publish$",
        FormBuilderViewSet.as_view({"post": "publish"})),
    re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/unpublish$",
        FormBuilderViewSet.as_view({"post": "unpublish"})),
    re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/duplicate$",
        FormBuilderViewSet.as_view({"post": "duplicate"})),
    re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/versions$",
        FormBuilderViewSet.as_view({"get": "versions"})),
    re_path(r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)$",
        FormBuilderViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"})),
    re_path(r"^(?P<version>(v1))/manage/forms$",
        FormBuilderViewSet.as_view({"get": "list", "post": "create"})),
]
```

Note: `POST /api/v1/forms` and `GET /api/v1/forms` share the same `list_form` view, which dispatches by method internally. There is no separate `create_form` URL entry.

All new views receive a `version` kwarg from the URL regex — view signatures are `def view_name(request, version, pk)`.

---

### Group H: `list_form` (backward compat) ✅

`list_form` handles `GET /api/v1/forms` only — flat array, no auth, no pagination. It coexists with `FormBuilderViewSet` which handles all form builder CRUD at `/manage/forms/...`. The DRF double-wrap issue (`_handle_create_form`) is gone because the ViewSet owns creation.

---

## Testing Requirements ✅

Tests split by domain into six files under `backend/api/v1/v1_forms/tests/`:

| File | TestCase class | Covers |
|---|---|---|
| `tests_manage_form_list.py` | `ManageFormListTestCase` | `GET /api/v1/forms` (flat) + `GET /api/v1/manage/forms` (paginated) + retrieve |
| `tests_manage_form_create.py` | `ManageFormCreateTestCase` | `POST /api/v1/manage/forms` |
| `tests_manage_form_update.py` | `ManageFormUpdateTestCase` | `PUT` — update draft/published, add/edit/delete question, add/edit/delete option |
| `tests_manage_form_soft_delete.py` | `ManageFormSoftDeleteTestCase` | Soft-delete vs hard-delete behavior; `allow_delete` guard |
| `tests_manage_form_publish.py` | `ManageFormPublishTestCase` | `publish`, `duplicate`, `versions`, `activate` |
| `tests_manage_form_delete.py` | `ManageFormDeleteTestCase` | `DELETE /api/v1/manage/forms/{id}` |

Each class uses `@override_settings(USE_TZ=False, TEST_ENV=True)` and resets PostgreSQL sequences in `setUp` to avoid PK conflicts with seeded IDs.

### List / Retrieve (ManageFormListTestCase)

| Test | Status |
|---|---|
| `test_list_forms_includes_status` | ✅ |
| `test_list_forms_no_auth_allowed` | ✅ |
| `test_manage_list_requires_auth` | ✅ |
| `test_manage_list_returns_paginated` | ✅ |
| `test_get_form_includes_status` | ✅ |
| `test_get_form_not_found` | ✅ |
| `test_get_form_disable_delete_in_response` | ✅ |

### Create (ManageFormCreateTestCase)

| Test | Status |
|---|---|
| `test_create_draft_form` | ✅ |
| `test_create_requires_auth` | ✅ |
| `test_create_missing_name_returns_400` | ✅ |
| `test_create_invalid_question_type` | ✅ |
| `test_create_with_image_type` | ✅ |
| `test_create_with_option_question` | ✅ |
| `test_create_name_autogenerated_if_missing` | ✅ |
| `test_create_type_as_integer` | ✅ |

### Update (ManageFormUpdateTestCase)

| Test | Status |
|---|---|
| `test_update_draft_form_returns_200` | ✅ |
| `test_update_partial_payload_keeps_existing_fields` | ✅ |
| `test_update_add_question` | ✅ |
| `test_update_edit_question` | ✅ |
| `test_update_delete_question_without_answers` | ✅ |
| `test_update_add_option` | ✅ |
| `test_update_edit_option` | ✅ |
| `test_update_delete_option` | ✅ |
| `test_update_published_increments_version_in_place` | ✅ |
| `test_update_draft_keeps_version` | ✅ |
| `test_update_published_in_place_real_ids` | ✅ |

### Soft-Delete (ManageFormSoftDeleteTestCase)

| Test | Status |
|---|---|
| `test_update_cannot_delete_group_with_answers` | ✅ |
| `test_update_cannot_delete_question_with_answers` | ✅ |
| `test_update_allow_delete_question_with_answers` | ✅ |
| `test_soft_delete_question_preserves_db_row` | ✅ |
| `test_soft_delete_group_with_allow_delete` | ✅ |
| `test_hard_delete_question_row_is_gone` | ✅ |

### Publish / Versions / Activate (ManageFormPublishTestCase)

| Test | Status |
|---|---|
| `test_publish_form` | ✅ |
| `test_publish_not_found` | ✅ |
| `test_publish_creates_snapshot` | ✅ |
| `test_publish_snapshot_excludes_soft_deleted` | ✅ |
| `test_publish_creates_new_snapshot_on_republish` | ✅ |
| `test_duplicate_form` | ✅ |
| `test_versions_empty_for_draft` | ✅ |
| `test_versions_returns_published_versions` | ✅ |
| `test_activate_changes_active_version` | ✅ |
| `test_activate_wrong_form_returns_404` | ✅ |

### Delete (ManageFormDeleteTestCase)

| Test | Status |
|---|---|
| `test_delete_form_without_submissions` | ✅ |
| `test_delete_form_not_found` | ✅ |
| `test_delete_form_with_submissions_returns_409` | ✅ |
| `test_delete_requires_superuser` | ✅ |

Run all:
```bash
./dc.sh exec backend python manage.py test \
  api.v1.v1_forms.tests.tests_manage_form_list \
  api.v1.v1_forms.tests.tests_manage_form_create \
  api.v1.v1_forms.tests.tests_manage_form_update \
  api.v1.v1_forms.tests.tests_manage_form_soft_delete \
  api.v1.v1_forms.tests.tests_manage_form_publish \
  api.v1.v1_forms.tests.tests_manage_form_delete
```

---

### Group I: Granular Permission Foundation (FB-009 anticipation) ✅

**Files**: `v1_profile/constants.py`, `utils/custom_permissions.py`, `v1_forms/views.py`, `v1_profile/management/commands/default_roles_seeder.py`

#### `v1_profile/constants.py` — five granular `FeatureAccessTypes`

```python
class FeatureAccessTypes:
    invite_user = 1
    form_view = 3
    form_create = 4
    form_edit = 5
    form_publish = 6
    form_delete = 7

    FieldStr = {
        invite_user: "Invite User",
        form_view: "Form View",
        form_create: "Form Create",
        form_edit: "Form Edit",
        form_publish: "Form Publish",
        form_delete: "Form Delete",
    }

class FeatureTypes:
    ...
    FieldGroup = {
        user_access: [FeatureAccessTypes.invite_user],
        form_builder: [
            FeatureAccessTypes.form_view,
            FeatureAccessTypes.form_create,
            FeatureAccessTypes.form_edit,
            FeatureAccessTypes.form_publish,
            FeatureAccessTypes.form_delete,
        ],
    }
```

#### `utils/custom_permissions.py` — `FormBuilderAccess` factory

```python
def FormBuilderAccess(required_access):
    """Return a permission class for the given granular access type."""
    class _Permission(BasePermission):
        def has_permission(self, request, view):
            if request.user.is_superuser:
                return True
            return request.user.user_user_role.filter(
                role__role_role_feature_access__type=FeatureTypes.form_builder,
                role__role_role_feature_access__access=required_access,
            ).exists()
    return _Permission
```

#### `v1_forms/views.py` — per-operation permission gates

- `_handle_create_form`: `FormBuilderAccess(form_create)().has_permission(request, None)`
- `form_detail` decorator: `FormBuilderAccess(form_view)` outer; inline check `FormBuilderAccess(form_edit)` on PUT
- `publish_form`: `FormBuilderAccess(form_publish)`
- `duplicate_form_view`: `FormBuilderAccess(form_create)`
- `form_versions`: `FormBuilderAccess(form_view)`

#### `default_roles_seeder.py` — seed five granular access rows per admin role

```python
for access in [
    FeatureAccessTypes.form_view,
    FeatureAccessTypes.form_create,
    FeatureAccessTypes.form_edit,
    FeatureAccessTypes.form_publish,
    FeatureAccessTypes.form_delete,
]:
    admin_role.role_role_feature_access.create(
        type=FeatureTypes.form_builder, access=access
    )
```

---

## Handoff Notes for FB-003

After this spec is delivered, FB-003 frontend can start. Key contracts FB-003 depends on:

| Contract | Detail |
|---|---|
| `POST /api/v1/manage/forms` → 201 | Response includes `{ id, status: "draft", version: 1, ... }` |
| `PUT /api/v1/manage/forms/{id}` → 200 | Always `200`, both draft and published; draft saved in-place unchanged version; published form gets a new `FormPublishedVersion` snapshot and incremented `version`; partial payload supported |
| `POST /api/v1/manage/forms/{id}/publish` → 200 | Transitions draft → published (sets `status`, `published_at`); on re-publish of already-published form, adds new snapshot but leaves `status`/`published_at` unchanged |
| `GET /api/v1/manage/forms/{id}` | Includes `status`, `version`, `published_at`, `active_version_id`, `question_group` with `disable_delete` |
| `GET /api/v1/forms` | Flat array; items include `status` and `version` |
| `"image"` type | Only accepted string for image questions; stored as `QuestionTypes.image = 8` |
| `type` field | Accepts `1`/`2` (int) or `"registration"`/`"monitoring"` (string); defaults to `1` if omitted |
| Editor payload | View calls `_normalize_editor_payload()` before validation; `question_groups`/`questions`/`options` plural keys and camelCase field names are accepted |
| Permission | `FormBuilderAccess(access)` factory in `utils/custom_permissions.py`; five granular `FeatureAccessTypes` (`form_view=3` … `form_delete=7`) |
