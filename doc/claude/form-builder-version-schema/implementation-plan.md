# Implementation Plan: Form Schema Versioning (FB-002A)

**Branch**: `feature/229-fb-002-implement-backend-form-crud-api` (same branch as FB-002)  
**Status**: Groups A–E complete. Groups F and G pending.

---

## Prerequisites

- [x] FB-002 and FB-002A implemented in the same branch
- [x] Backend services running: `./dc.sh up -d`
- [x] Migrations 0008 and 0009 applied

---

## Task Breakdown

Tasks in the same group can run in parallel. Each group should be a single commit.

---

### Group A: Soft-Delete — Models, Migration, Functions, Serializers

**Requirements**: FR-1, FR-2, FR-3, FR-4  
**Status**: Partially done in FB-002 branch (model + migration generated). Completes the read-path filtering.

#### A-1: Models ✅ (done)

`QuestionGroup` and `Questions` both extend the project-standard `SoftDeletes` mixin (`utils/soft_deletes_model.py`), which adds `deleted_at = DateTimeField(null=True)` and provides `.soft_delete()`, `.hard_delete()`, `.restore()`, and three managers (`objects` filters active rows; `objects_deleted`; `objects_with_deleted`).  
Conditional `UniqueConstraint(condition=Q(deleted_at__isnull=True))` replaces `unique_together` + named constraint.  
**File**: `backend/api/v1/v1_forms/models.py`

#### A-2: Migration ✅ (done)

`0008_remove_questiongroup_unique_form_question_group_and_more.py` — adds `deleted_at DateTimeField(null=True)` to both tables; removes old `unique_together` and named constraints; adds new conditional `UniqueConstraint` on each.

#### A-3: functions.py — Soft-delete on `allow_delete=True`, `objects_with_deleted` for restore ✅ (done in FB-002 branch)

**File**: `backend/api/v1/v1_forms/functions.py`

`SoftDeletes` default manager auto-filters `deleted_at__isnull=True`, so the queryset already contains only active questions/groups.

`_save_questions` and the group update block both use `objects_with_deleted` when looking up existing IDs from the payload. This means including a soft-deleted question or group ID in a PUT payload **restores** that row (clears `deleted_at`) instead of raising a "not found" error or creating a duplicate.

In `_save_questions`:
```python
# SoftDeletes default manager auto-filters deleted rows.
questions_to_remove = group.question_group_question.exclude(
    id__in=incoming_q_ids
)
if not allow_delete:
    for q in questions_to_remove:
        if Answers.objects.filter(question=q).exists():
            raise ValueError(f"Can't delete question|Question {q.id} has answers")
    # Hard-delete: no answers exist, row is safe to remove entirely.
    questions_to_remove.hard_delete()
else:
    # Soft-delete: preserve row so historical Answers FKs stay valid (FB-002A).
    questions_to_remove.soft_delete()
```

In `save_form` (group-level):
```python
# SoftDeletes default manager auto-filters deleted rows.
groups_to_remove = form.form_question_group.exclude(id__in=incoming_group_ids)

if not allow_delete:
    # existing answers guard unchanged
    ...
    # Hard-delete: Django CASCADE hard-deletes child questions automatically.
    groups_to_remove.hard_delete()
else:
    # Soft-delete: FK cascade doesn't apply to soft-delete, update explicitly.
    for grp in groups_to_remove:
        grp.question_group_question.soft_delete()
    groups_to_remove.soft_delete()
```

#### A-4: serializers.py — Filter `deleted_at__isnull=True` everywhere ✅ (done in FB-002 branch)

**File**: `backend/api/v1/v1_forms/serializers.py`

Add import at the top:
```python
from api.v1.v1_data.models import Answers
```
Remove the inline `from api.v1.v1_data.models import Answers` inside `get_disable_delete`.

Update all six queryset calls:

| Serializer | Queryset | After |
|---|---|---|
| `ListQuestionGroupSerializer.get_question` | `.all()` | `.filter(deleted_at__isnull=True)` |
| `WebFormDetailSerializer.get_question_group` | `.all()` | `.filter(deleted_at__isnull=True)` |
| `FormDataQuestionGroupSerializer.get_question` | `.all()` | `.filter(deleted_at__isnull=True)` |
| `FormDataSerializer.get_question_group` | `.all()` | `.filter(deleted_at__isnull=True)` |
| `FormDetailQuestionGroupSerializer.get_question` | `.all()` | `.filter(deleted_at__isnull=True)` |
| `FormDetailSerializer.get_question_group` | `.all()` | `.filter(deleted_at__isnull=True)` |

Also filter `get_cascades` direct query:
```python
cascade_questions = Questions.objects.filter(
    type__in=[QuestionTypes.cascade, QuestionTypes.administration],
    form=instance,
    deleted_at__isnull=True,
).all()
```

**Verify**:
```bash
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests
```

---

### Group B: `FormPublishedVersion` Model and Migrations ✅ (done)

**Requirements**: FR-5, FR-6, FR-7, FR-8, FR-11, FR-12

#### B-1: New model

**File**: `backend/api/v1/v1_forms/models.py`

```python
class FormPublishedVersion(models.Model):
    """Immutable snapshot of a form's question structure at publish time.

    Created by POST /manage/forms/{id}/publish. Never modified after creation.
    FormData.published_version references this to enable rendering historical
    submissions against the exact schema used at collection time.
    """
    form = models.ForeignKey(
        Forms,
        on_delete=models.CASCADE,
        related_name="published_versions",
    )
    # Auto-incremented per form by the publish action. Not a global counter.
    version = models.IntegerField()
    # Full JSON snapshot of question_group[] at publish time (see design.md).
    # Includes all questions that were active (is_deleted=False) at that moment.
    schema = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        "v1_users.SystemUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="published_form_versions",
    )

    class Meta:
        unique_together = ("form", "version")
        ordering = ["form", "version"]
        db_table = "form_published_version"
```

#### B-2: Add `active_version` to `Forms`

**File**: `backend/api/v1/v1_forms/models.py`

```python
# Points to the FormPublishedVersion currently used for data collection.
# Null while the form is a draft (no published version yet).
# Changed by POST .../publish (auto) and POST .../activate/{id} (manual rollback).
active_version = models.ForeignKey(
    "FormPublishedVersion",
    on_delete=models.SET_NULL,
    related_name="active_for_forms",
    null=True,
    blank=True,
    default=None,
)
```

#### B-3: Add `published_version` to `FormData`

**File**: `backend/api/v1/v1_data/models.py`

```python
# Records which FormPublishedVersion was active at submission time.
# Null for submissions collected before FB-002A was deployed (backward compat).
published_version = models.ForeignKey(
    "v1_forms.FormPublishedVersion",
    on_delete=models.SET_NULL,
    related_name="form_data",
    null=True,
    blank=True,
    default=None,
)
```

#### B-4: Run makemigrations

```bash
./dc.sh exec backend python manage.py makemigrations
```

Expected: two new migration files — one for `v1_forms` (FormPublishedVersion + Forms.active_version), one for `v1_data` (FormData.published_version).

**Verify**:
```bash
./dc.sh exec backend python manage.py migrate
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests
```

---

### Group C: Snapshot Creation in `publish` Action ✅ (done)

**Requirements**: FR-5, FR-6

#### C-1: Snapshot helper in `functions.py` ✅

**File**: `backend/api/v1/v1_forms/functions.py`

Add `_build_schema_snapshot(form)`:
```python
def _build_schema_snapshot(form):
    """Build the immutable schema JSON stored in FormPublishedVersion.schema.

    Captures all active (is_deleted=False) question groups and their questions
    at the moment of publish. This snapshot is never modified after creation
    and is used to render historical submissions even after questions are deleted.
    """
    groups = []
    for group in form.form_question_group.filter(
        deleted_at__isnull=True
    ).order_by("order"):
        questions = []
        for q in group.question_group_question.filter(
            deleted_at__isnull=True
        ).order_by("order"):
            questions.append({
                "id": q.id,
                "order": q.order,
                "name": q.name,
                "label": q.label,
                "short_label": q.short_label,
                "type": QuestionTypes.FieldStr.get(q.type),
                "meta": q.meta,
                "required": q.required,
                "rule": q.rule,
                "dependency": q.dependency,
                "dependency_rule": q.dependency_rule,
                "api": q.api,
                "extra": q.extra,
                "tooltip": q.tooltip,
                "fn": q.fn,
                "pre": q.pre,
                "display_only": q.display_only,
                "option": list(
                    q.options.values("order", "label", "value", "other", "color")
                ),
            })
        groups.append({
            "id": group.id,
            "name": group.name,
            "label": group.label,
            "order": group.order,
            "repeatable": group.repeatable,
            "repeat_text": group.repeat_text,
            "question": questions,
        })
    return {"version": form.version, "question_group": groups}
```

Add `create_published_version(form, user)`:
```python
@transaction.atomic
def create_published_version(form, user):
    """Create a FormPublishedVersion snapshot and set it as active_version.

    Called by the publish action AND automatically by the update action
    whenever the form is already published. Forms.version is always synced
    to match the new snapshot's version counter.

    status and published_at are only set on the draft→published transition.
    Already-published re-saves skip those fields to preserve the original
    published_at date.
    """
    last = form.published_versions.order_by("-version").first()
    next_version = (last.version + 1) if last else 1

    snapshot = _build_schema_snapshot(form)
    snapshot["version"] = next_version

    pv = FormPublishedVersion.objects.create(
        form=form,
        version=next_version,
        schema=snapshot,
        published_by=user,
    )
    form.active_version = pv
    form.version = next_version
    update_fields = ["active_version", "version"]

    if form.status != FormStatus.published:
        # Draft → published: set status and record the publish date.
        form.status = FormStatus.published
        form.published_at = pv.published_at
        update_fields.extend(["status", "published_at"])

    form.save(update_fields=update_fields)
    return pv
```

#### C-2: Update `publish` action and `update` action in `views.py` ✅ (done)

**File**: `backend/api/v1/v1_forms/views.py`

`publish` action — no "already published" guard; every call creates a new snapshot:

```python
@action(detail=True, methods=["post"])
def publish(self, request, *args, **kwargs):
    form = self.get_object()
    create_published_version(form, request.user)
    return Response(FormDetailSerializer(instance=form).data)
```

`update` action — after `save_form`, automatically calls `create_published_version` if the form is published:

```python
def update(self, request, *args, **kwargs):
    form = self.get_object()
    data = _normalize_editor_payload(request.data)
    ...
    updated = save_form(data, instance=form)
    if updated.status == FormStatus.published:
        create_published_version(updated, request.user)
    return Response(FormDetailSerializer(instance=updated).data)
```

`create_published_version` handles setting `form.version`, `form.active_version`, and (on first publish only) `form.status` and `form.published_at`, atomically.

**Verify**:
```bash
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests.tests_manage_form_update
```

---

### Group D: `versions` Endpoint — Return `FormPublishedVersion` ✅ (done)

**Requirements**: FR-13

#### D-1: New serializer ✅

**File**: `backend/api/v1/v1_forms/serializers.py`

```python
class FormPublishedVersionSerializer(serializers.ModelSerializer):
    """Serializer for the versions list endpoint.

    is_active is computed relative to the form's current active_version.
    published_by is the email of the user who triggered the publish.
    """
    published_by = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    def get_published_by(self, instance):
        return instance.published_by.email if instance.published_by else None

    def get_is_active(self, instance):
        form = instance.form
        return form.active_version_id == instance.id

    class Meta:
        model = FormPublishedVersion
        fields = ["id", "version", "published_at", "published_by", "is_active"]
```

#### D-2: Update `versions` action in `views.py`

**File**: `backend/api/v1/v1_forms/views.py`

Replace the `versions` action to use `FormPublishedVersion`:
```python
@action(detail=True, methods=["get"])
def versions(self, request, *args, **kwargs):
    form = self.get_object()
    # Return all published version snapshots for this form, not the old
    # previous_version FK chain (which is never populated after FB-002).
    published = form.published_versions.all().order_by("version")
    return Response(
        FormPublishedVersionSerializer(published, many=True).data
    )
```

---

### Group E: `activate` Endpoint ✅ (done)

**Requirements**: FR-14, NFR-4

**File**: `backend/api/v1/v1_forms/views.py`

Add `activate` as a custom action with `url_path="activate/(?P<version_id>[^/.]+)"`. Calls `restore_from_snapshot` to perform a structural rollback (not just an `active_version` pointer update):

```python
@extend_schema(
    tags=["Manage Forms"],
    summary="Set a specific published version as the active schema",
    request=None,
)
@action(
    detail=True,
    methods=["post"],
    url_path=r"activate/(?P<version_id>[^/.]+)",
)
def activate(self, request, version_id=None, *args, **kwargs):
    form = self.get_object()
    # Validate the version belongs to this form (NFR-4).
    pv = get_object_or_404(form.published_versions, pk=version_id)
    restore_from_snapshot(form, pv)
    return Response(FormDetailSerializer(instance=form).data)
```

`restore_from_snapshot` (in `functions.py`) performs a two-pass atomic operation:
- **Pass 1**: soft-deletes active questions/groups absent from the snapshot.
- **Pass 2**: restores snapshot rows via `objects_with_deleted` (clears `deleted_at`) and syncs all fields including options.
- Sets `form.active_version = pv`.

Register the URL pattern in `urls.py`:
```python
re_path(
    r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/activate/(?P<version_id>[0-9]+)$",
    FormBuilderViewSet.as_view({"post": "activate"}),
),
```

---

### Group F: Serve Schema from `active_version` on Web/Mobile Endpoints ⏳ (pending)

**Requirements**: FR-9, FR-10, D-1

#### F-1: `web_form_details` view

**File**: `backend/api/v1/v1_forms/views.py`

In `web_form_details`, replace the serializer call with a snapshot-aware branch:
```python
instance = get_object_or_404(Forms, pk=form_id)
if not instance.active_version:
    # Draft forms have no published schema — not available for data collection.
    raise Http404
# Serve the frozen snapshot instead of live question tables so the rendered
# form exactly matches what will be stored in FormData.published_version.
schema = instance.active_version.schema
# ... return schema directly or via serializer
```

#### F-2: `list_form` / `form_data` (mobile flat endpoint)

**File**: `backend/api/v1/v1_forms/views.py`

Similarly guard with `active_version` check and serve from snapshot.

---

### Group G: Set `published_version` on FormData Submission ⏳ (pending)

**Requirements**: FR-11

**File**: `backend/api/v1/v1_data/views.py` (or wherever `FormData` is created)

When creating a new `FormData` record, set:
```python
form = get_object_or_404(Forms, pk=form_id)
form_data = FormData.objects.create(
    form=form,
    published_version=form.active_version,  # snapshot active at submission time
    ...
)
```

---

### Group H: Tests ✅ (done — Groups A–E; F and G tests pending)

**Files**:
- `backend/api/v1/v1_forms/tests/tests_manage_form_soft_delete.py` (new)
- `backend/api/v1/v1_forms/tests/tests_manage_form_publish.py` (new)
- `backend/api/v1/v1_forms/tests/tests_manage_form_update.py` (trimmed to pure PUT tests)

#### `tests_manage_form_soft_delete.py` — `ManageFormSoftDeleteTestCase`

| Test | Covers |
|---|---|
| `test_update_cannot_delete_group_with_answers` | PUT without `allow_delete` → 400 |
| `test_update_cannot_delete_question_with_answers` | Same for question |
| `test_update_allow_delete_question_with_answers` | PUT `allow_delete=true` → API hides question |
| `test_soft_delete_question_preserves_db_row` | DB row survives with `deleted_at` set; Answer FK intact |
| `test_soft_delete_group_with_allow_delete` | Group + its questions soft-deleted; Answer FK intact |
| `test_hard_delete_question_row_is_gone` | Question with no answers: row completely removed (not in `objects_with_deleted`) |

#### `tests_manage_form_publish.py` — `ManageFormPublishTestCase`

| Test | Covers |
|---|---|
| `test_publish_form` | POST publish → `status=published`, `published_at`, `version=1`, `active_version_id` set |
| `test_publish_not_found` | 404 on unknown form |
| `test_publish_creates_snapshot` | `FormPublishedVersion` created; `active_version` set; schema has `question_group` |
| `test_publish_snapshot_excludes_soft_deleted` | Soft-deleted questions absent from snapshot |
| `test_publish_creates_new_snapshot_on_republish` | Second publish → version 2 snapshot |
| `test_duplicate_form` | POST duplicate → new draft with `(Copy)` suffix |
| `test_versions_empty_for_draft` | GET versions on draft → `[]` |
| `test_versions_returns_published_versions` | GET versions → list with `is_active=true` |
| `test_activate_changes_active_version` | POST activate → `active_version_id` updated |
| `test_activate_wrong_form_returns_404` | POST activate with version from a different form → 404 |

#### Pending tests (Groups F and G)

| Test | Covers |
|---|---|
| `test_draft_form_web_endpoint_returns_404` | GET `/form/{id}` on draft → 404 (Group F) |
| `test_published_form_web_endpoint_serves_snapshot` | GET `/form/{id}` returns `active_version.schema` (Group F) |
| `test_form_data_records_published_version` | Submission sets `published_version_id` (Group G) |

**Run all**:
```bash
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests --verbosity=2
./dc.sh exec backend coverage run --rcfile=./.coveragerc manage.py test --shuffle --parallel 4
./dc.sh exec backend coverage report -m
```

---

## Implementation Order

```
Day 1 AM: Group A (soft-delete read-path filtering — serializers + functions)
Day 1 PM: Group B (FormPublishedVersion model + migrations)
Day 2 AM: Group C (snapshot creation, publish action update)
Day 2 PM: Group D (versions endpoint) + Group E (activate endpoint)
Day 3 AM: Group F (web/mobile endpoint schema serving)
Day 3 PM: Group G (FormData published_version on submission)
Day 4:    Group H (tests across all groups)
```

---

## Lint & Prettier

Run before every commit:
```bash
./dc.sh exec -T backend flake8
./dc.sh exec backend python manage.py test api.v1.v1_forms.tests --verbosity=1
```
