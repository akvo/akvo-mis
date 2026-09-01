"""Generate marked, disposable submission data (SEED-001).

Every row this command writes carries DUMMY_PREFIX so a human can tell
generated data from real data at a glance, and so `--clean` can remove it
again. See doc/design/SEED-tenant-aware-seeders.md.
"""
import re
import time as time_module
from datetime import datetime, timedelta, time

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.utils.timezone import make_aware
from django.db import transaction
from django.db.models import Max, Q
from faker import Faker

from api.v1.v1_data.constants import (
    DUMMY_EMAIL_DOMAIN,
    DUMMY_EMAIL_PREFIX,
    DUMMY_PREFIX,
)
from api.v1.v1_data.models import FormData
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.bbox import (
    get_bbox_attribute,
    random_point_in,
    resolve_bbox,
)
from api.v1.v1_profile.models import (
    Administration,
    DataAccessTypes,
    EntityData,
    Levels,
    Role,
)
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.constants import BBOX_ATTRIBUTE_NAME, TEST_GEO_DATA
from api.v1.v1_visualization.functions import refresh_materialized_data
from utils.tenant_command import resolve_tenant

fake = Faker()

DEFAULT_PASSWORD = "Test#123"


def mark_as_dummy(form_data):
    """Stamp the fake-data prefix, idempotently.

    MUST be called after add_fake_answers(), which rebuilds `name` from
    the form's meta questions and would otherwise discard the prefix, and
    before `save_to_file`, which serialises the name into the storage blob
    that mobile debugging reads.
    """
    if form_data.name.startswith(DUMMY_PREFIX):
        return form_data
    form_data.name = f"{DUMMY_PREFIX}{form_data.name}"
    form_data.save(update_fields=["name"])
    return form_data


def find_administration(name, level, tenant):
    """Name-matched lookup, walking up until a tier matches.

    Only used by --test, whose TEST_GEO_DATA names line up with
    DEFAULT_ADMINISTRATION_DATA. The normal path takes administrations
    from the database instead (pick_target_administrations), because no
    real workspace is named after a bundled fixture.
    """
    if level < 0:
        return None
    adm = Administration.objects.filter(
        name=name, level__level=level, tenant=tenant
    ).first()
    if adm is None:
        adm = find_administration(name, level - 1, tenant)
    return adm


def pick_target_administrations(tenant):
    """The leaf-most administrations datapoints may attach to."""
    qs = Administration.objects.filter(
        parent__isnull=False, tenant=tenant
    )
    if not qs.exists():
        return []
    # Deepest level present in THIS workspace. An install-wide max would
    # read across every tenant.
    deepest = qs.aggregate(m=Max("level__level"))["m"]
    return list(qs.filter(level__level=deepest).order_by("id"))


def require_targets_with_bbox(tenant):
    """The leaf units to seed onto, guaranteed to resolve a bounding box.

    Every row this command writes carries a `geo`, so the check runs before
    the transaction opens rather than leaving pinless rows behind (D-9).
    Returns (targets, attribute, cache) -- the cache is shared with the seed
    loop so each unit's box is read once.
    """
    targets = pick_target_administrations(tenant)
    if not targets:
        raise CommandError(
            "This workspace has no administration hierarchy below its root, "
            "so there is nothing to attach datapoints to. Import one first:\n"
            "  python manage.py administration_csv_seeder "
            "--source=administrations/<file>.csv --tenant=<subdomain>"
        )

    attribute = get_bbox_attribute(tenant)
    cache = {}
    with_bbox = [
        adm for adm in targets
        if resolve_bbox(adm, attribute, cache) is not None
    ]
    if not with_bbox:
        raise CommandError(
            "None of this workspace's administrations carry a "
            f"'{BBOX_ATTRIBUTE_NAME}' attribute, so generated datapoints "
            "would have no map coordinates.\n"
            "Re-import the hierarchy from a CSV carrying an "
            "'attr_Bounding Box' column -- the notebook in "
            "scripts/administration_csv_generator/ writes one by default:\n"
            "  python manage.py administration_csv_seeder "
            "--source=administrations/<file>.csv --tenant=<subdomain>"
        )
    return with_bbox, attribute, cache


def clean_dummy_data(tenant, stdout):
    """Hard-delete everything carrying DUMMY_PREFIX, in dependency order.

    The delete key is the prefix, never `created_by`: the seeder reuses an
    existing submitter when one matches, which on a shared workspace is a
    real person's account, and cascading from it would destroy their
    genuine submissions.
    """
    counts = {}

    def scoped(qs, path="tenant"):
        return qs.filter(**{path: tenant}) if tenant is not None else qs

    # Tier 1 -- datapoints. objects_with_deleted, not objects: the default
    # manager hides soft-deleted rows, so fake rows soft-deleted by an
    # earlier run would survive every subsequent --clean. Drafts are
    # included in the same queryset. Monitoring children cascade via
    # FormData.parent; Answers and AnswerHistory via their `data` FK.
    fake_data = scoped(
        FormData.objects_with_deleted.filter(
            name__startswith=DUMMY_PREFIX
        ),
        "form__tenant",
    )
    counts["FormData"] = fake_data.count()
    fake_data.hard_delete()

    # Tier 2 -- mobile assignments. Deleting them before their users keeps
    # the reported counts honest and covers assignments attached to a
    # REUSED real user, which tier 3 must not touch.
    assignments = scoped(
        MobileAssignment.objects.filter(name__startswith=DUMMY_PREFIX),
        "user__tenant",
    )
    counts["MobileAssignment"] = assignments.count()
    assignments.delete()

    # Tier 3 -- seeded accounts, guarded. Only accounts the seeder minted,
    # and only those with no surviving FormData.
    orphaned = scoped(
        SystemUser.objects_with_deleted.filter(
            email__startswith=DUMMY_EMAIL_PREFIX,
            email__endswith=DUMMY_EMAIL_DOMAIN,
        ).exclude(form_data_created__isnull=False)
    )
    counts["SystemUser"] = orphaned.count()
    orphaned.hard_delete()

    # The materialized view carries a PROTECT on its administration FK,
    # and still holds rows for the datapoints tier 1 just removed. Refresh
    # it here so tier 4 is not blocked by a stale view -- and so the view
    # stops serving deleted datapoints, which it must not do regardless.
    refresh_materialized_data()

    # Tier 4 -- generated administrations, deepest level first: the
    # self-referential PROTECT on Administration.parent means a parent
    # cannot go before its children.
    fake_admins = scoped(
        Administration.objects.filter(name__startswith=DUMMY_PREFIX)
    )
    counts["Administration"] = fake_admins.count()
    if counts["Administration"]:
        # EntityData PROTECTs its administration, and entity-cascade
        # answers create rows against whichever unit the datapoint used.
        # These belong to units being removed, so they go too -- unlike
        # entity data attached to real administrations, which is kept.
        EntityData.objects.filter(administration__in=fake_admins).delete()
        depths = sorted(
            fake_admins.values_list("level__level", flat=True).distinct(),
            reverse=True,
        )
        for level_depth in depths:
            fake_admins.filter(level__level=level_depth).delete()

    # Tier 5 -- generated levels, only once nothing is left at them.
    # Levels CASCADE to Administration, so an unguarded delete here would
    # silently take real units with it.
    fake_levels = scoped(
        Levels.objects.filter(name__startswith=DUMMY_PREFIX)
    ).exclude(administrator_level__isnull=False)
    counts["Levels"] = fake_levels.count()
    fake_levels.delete()

    stdout.write("-- Cleaning fake data")
    for label, count in counts.items():
        stdout.write(f"   {label:<20} {count}")
    return counts


def pick_role(data_access, level, tenant):
    """A role at this level, or any role with the same access.

    UserRole.role is not nullable, so returning None here is an
    IntegrityError several frames later. Generated hierarchies (D-10)
    create levels that default_roles_seeder never saw, so the level-exact
    lookup legitimately misses and the fallback carries it.
    """
    base = Role.objects.filter(
        role_role_access__data_access=data_access, tenant=tenant
    )
    role = base.filter(administration_level=level).order_by("?").first()
    if role:
        return role
    role = base.order_by("?").first()
    if role:
        return role
    raise CommandError(
        "This workspace has no role granting "
        f"'{DataAccessTypes.FieldStr.get(data_access, data_access)}' "
        "access. Run default_roles_seeder first."
    )


def create_approver_user(administration, org, tenant):
    """Create a new approver user for the given administration."""
    da = DataAccessTypes.approve
    adm_name = re.sub(r"[^A-Za-z0-9]+", ".", administration.name.lower())
    fake_digit = fake.random_digit_not_null()
    approver_email = "{0}approver.{1}{2}{3}".format(
        DUMMY_EMAIL_PREFIX, adm_name, fake_digit, DUMMY_EMAIL_DOMAIN
    )
    approver = SystemUser.objects.filter(
        Q(
            user_user_role__role__role_role_access__data_access=da,
            user_user_role__administration=administration,
        ) | Q(email=approver_email)
    ).order_by("?").first()
    if not approver:
        # Check if a deleted user with the same email exists
        approver = SystemUser.objects_deleted.filter(
            email=approver_email
        ).first()
        if approver:
            approver.restore()
            return
    approver = SystemUser.objects.create_user(
        email=approver_email,
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        phone_number=fake.phone_number()[:15],
        organisation=org,
        tenant=tenant,
    )
    approver.set_password(DEFAULT_PASSWORD)
    approver.save()
    forms = Forms.objects.filter(parent__isnull=True, tenant=tenant)
    for form in forms:
        approver.user_form.create(form=form)
    approver.save()

    role = pick_role(da, administration.level, tenant)
    approver.user_user_role.create(
        role=role,
        administration=administration,
    )


def create_approvers_recursively(
    administration,
    org,
    tenant,
    max_depth: int = 3,
    current_depth: int = 0,
):
    """Create approvers for an administration and its descendants."""
    if current_depth >= max_depth:
        return
    create_approver_user(
        administration=administration, org=org, tenant=tenant
    )
    if administration.parent_administration.exists():
        child_admin = administration.parent_administration\
            .order_by("?").first()
        create_approvers_recursively(
            administration=child_admin,
            org=org,
            tenant=tenant,
            max_depth=max_depth,
            current_depth=current_depth + 1,
        )


class Command(BaseCommand):
    help = (
        "Generate DUMMY- prefixed submission data for one workspace. "
        "Use --clean to remove everything a previous run created."
    )

    def add_arguments(self, parser):
        boolean = lambda x: x.lower() in ('true', '1', 'yes', 'on')  # noqa: E731,E501
        parser.add_argument(
            "-r", "--repeat", nargs="?", const=5, default=5, type=int
        )
        parser.add_argument(
            "-m", "--monitoring", nargs="?", const=2, default=2, type=int
        )
        parser.add_argument(
            "--approved",
            type=boolean,
            default=True,
            help=(
                "true (default): every row is approved -- no pending "
                "rows, no approver accounts created. false: half the "
                "rows per form are left pending and an approver tree is "
                "built for them."
            ),
        )
        parser.add_argument(
            "--draft",
            type=boolean,
            default=False,
            help=(
                "Also create draft submissions. Contradicts "
                "--approved true."
            ),
        )
        parser.add_argument(
            "--test",
            type=boolean,
            default=False,
            help=(
                "Use the bundled TEST_GEO_DATA fixture, which carries its "
                "own coordinates. Exempt from --tenant."
            ),
        )
        parser.add_argument(
            "-t", "--tenant", type=str, default=None,
            help=(
                "Workspace subdomain to seed into. Required unless "
                "--test. 'default' exists on any migrated database."
            ),
        )
        parser.add_argument(
            "--clean",
            nargs="?",
            const=True,
            type=boolean,
            default=False,
            help=(
                "Hard-delete every DUMMY- row this workspace owns, then "
                "exit. Seeds nothing. To reset, run this and then a normal "
                "seed. Bounding boxes are left alone -- they belong to the "
                "hierarchy, not to the generated data."
            ),
        )

    def handle(self, *args, **options):
        repeat = options.get("repeat")
        monitoring = options.get("monitoring", 1)
        is_approved = options.get("approved", True)
        is_draft = options.get("draft", False)
        is_test = options.get("test", False)
        clean = options.get("clean", False)

        if is_approved and is_draft:
            raise CommandError(
                "--draft true contradicts --approved true: approved data "
                "has no drafts. Pass --approved false to seed a mixed "
                "workflow."
            )
        if clean and not settings.DEBUG:
            raise CommandError(
                "--clean is refused when DEBUG=False. This hard-deletes "
                "rows and is a development tool; it must never run "
                "against a production configuration."
            )

        # --test drives a closed fixture seeded with tenant=None, which
        # is how all 34 existing callers invoke this command.
        tenant = resolve_tenant(
            options.get("tenant"), required=not is_test
        )
        if clean:
            # Terminal, not a prelude to seeding. `--clean` reads as an
            # imperative, so a run that quietly repopulated afterwards
            # looked exactly like a clean that had failed.
            with transaction.atomic():
                clean_dummy_data(tenant, self.stdout)
            refresh_materialized_data()
            self.stdout.write(self.style.SUCCESS("-- Fake data cleared"))
            return

        now_date = datetime.now()
        start_date = now_date - timedelta(days=5 * 365)
        end_date = now_date - timedelta(days=30)
        base_created = fake.date_between(start_date, end_date)
        base_created = datetime.combine(base_created, time.min)
        base_created = make_aware(base_created)

        bbox_attribute = None
        bbox_cache = {}
        if is_test:
            last_level_obj = Levels.objects.filter(
                tenant=tenant
            ).order_by("-level").first()
            last_level = last_level_obj.level if last_level_obj else 0
            targets = [
                find_administration(geo["name"], last_level, tenant)
                for geo in TEST_GEO_DATA
            ]
            geos = [[geo["Y"], geo["X"]] for geo in TEST_GEO_DATA]
            targets = [adm for adm in targets if adm is not None]
            if not targets:
                raise CommandError(
                    "No administrations available to attach datapoints to."
                )
        else:
            targets, bbox_attribute, bbox_cache = require_targets_with_bbox(
                tenant
            )
            geos = None
            self.stdout.write(
                f"-- {len(targets)} administrations with a bounding box"
            )

        da = DataAccessTypes.approve
        ds = DataAccessTypes.submit
        filter_submitter = {
            "user_user_role__role__role_role_access__data_access": ds,
        }
        filter_approver = {
            "user_user_role__role__role_role_access__data_access": da,
        }

        form_data_counts = {}
        form_monitoring_counts = {}
        form_pending_counts = {}
        form_draft_counts = {}

        current_created = base_created
        total_points = len(targets)
        index = 0

        existing_data_count = FormData.objects.filter(
            is_pending=False,
            is_draft=False,
            name__startswith=DUMMY_PREFIX,
        ).count()
        if existing_data_count > 0:
            index = existing_data_count % total_points

        root_forms = Forms.objects.filter(
            parent__isnull=True, tenant=tenant
        )

        try:
            with transaction.atomic():
                for r in range(repeat):
                    if index >= total_points:
                        index = 0
                    adm = targets[index]
                    if geos:
                        geo_value = geos[index % len(geos)]
                    else:
                        # require_targets_with_bbox filtered `targets` to
                        # units that resolve, so this cannot be None.
                        geo_value = random_point_in(
                            resolve_bbox(adm, bbox_attribute, bbox_cache)
                        )
                    parent_adm = adm.ancestors.exclude(
                        parent__isnull=True
                    ).first() if adm.path else None
                    if not parent_adm:
                        parent_adm = adm
                    org = Organisation.objects.filter(
                        tenant=tenant
                    ).order_by("?").first()
                    user = SystemUser.objects.filter(
                        **filter_submitter,
                        user_user_role__administration=parent_adm,
                        tenant=tenant,
                    ) \
                        .exclude(password__exact="") \
                        .order_by("?").first()
                    if not user:
                        # Append a nanosecond timestamp so repeated calls
                        # within the same run never collide on Faker's
                        # finite user_name() pool.
                        email = (
                            f"{DUMMY_EMAIL_PREFIX}user."
                            f"{time_module.time_ns()}{DUMMY_EMAIL_DOMAIN}"
                        )
                        user = SystemUser.objects.create_user(
                            email=email,
                            first_name=fake.first_name(),
                            last_name=fake.last_name(),
                            phone_number=fake.phone_number()[:15],
                            organisation=org,
                            tenant=tenant,
                        )
                        user.set_password(DEFAULT_PASSWORD)

                        role = pick_role(ds, parent_adm.level, tenant)
                        user.user_user_role.create(
                            role=role,
                            administration=parent_adm,
                        )

                    if not user.user_form.exists():
                        for form in root_forms:
                            user.user_form.create(form=form)
                        user.save()

                    p = f"{parent_adm.path}{parent_adm.id}."
                    mobile_user = user.mobile_assignments \
                        .filter(administrations__path__startswith=p) \
                        .order_by("?").first()
                    if not mobile_user:
                        uname = (
                            f"{DUMMY_PREFIX}{adm.name.lower()}."
                            f"{fake.user_name()}"
                        )
                        mobile_user = MobileAssignment.objects \
                            .create_assignment(
                                user=user,
                                name=uname,
                                passcode=fake.lexify('????????'),
                            )
                    adm_children = parent_adm.parent_administration \
                        .order_by("?").first()
                    if adm_children:
                        mobile_user.administrations.set(
                            adm_children.parent_administration.all()
                            or [adm_children]
                        )
                    else:
                        mobile_user.administrations.set([parent_adm])
                    mobile_user.forms.set(
                        [uf.form for uf in user.user_form.all()]
                    )
                    mobile_user.save()

                    if not is_approved:
                        approver = SystemUser.objects.filter(
                            **filter_approver,
                            user_user_role__administration=parent_adm,
                            tenant=tenant,
                        ).order_by("?").first()
                        if not approver:
                            create_approvers_recursively(
                                administration=parent_adm,
                                org=org,
                                tenant=tenant,
                                max_depth=3,
                                current_depth=0,
                            )

                    for f in root_forms:
                        if not user.user_form.filter(form=f).exists():
                            continue

                        if f.name not in form_data_counts:
                            form_data_counts[f.name] = 0
                            form_monitoring_counts[f.name] = 0
                            form_pending_counts[f.name] = 0
                            form_draft_counts[f.name] = 0

                        name = f"{adm.full_name} - {fake.sentence(nb_words=3)}"
                        data_is_draft = is_draft and (
                            form_data_counts[f.name] % 2 == 1
                        )
                        data_is_pending = (
                            not is_approved and
                            (form_data_counts[f.name] % 2 == 1)
                        )

                        current_created += timedelta(days=1)

                        form_data = FormData.objects.create(
                            uuid=fake.uuid4(),
                            name=name,
                            form=f,
                            administration=adm,
                            created_by=user,
                            geo=geo_value,
                            is_pending=data_is_pending,
                            is_draft=False,
                        )
                        form_data.created = current_created
                        form_data.updated = current_created
                        form_data.save()
                        add_fake_answers(form_data)
                        # After add_fake_answers, which rebuilds `name`
                        # from meta questions and would discard the
                        # prefix; before save_to_file, which serialises
                        # the name into the storage blob.
                        mark_as_dummy(form_data)

                        form_data_counts[f.name] += 1
                        if data_is_pending:
                            form_pending_counts[f.name] += 1
                        if data_is_draft:
                            form_draft_counts[f.name] += 1
                            draft_data = FormData.objects.create(
                                uuid=fake.uuid4(),
                                name=f"{fake.sentence(nb_words=3)} - Draft",
                                form=f,
                                administration=adm,
                                created_by=user,
                                geo=geo_value,
                                is_pending=False,
                                is_draft=True,
                            )
                            draft_data.created = current_created
                            draft_data.updated = current_created
                            draft_data.save()

                            add_fake_answers(draft_data)
                            mark_as_dummy(draft_data)

                            if draft_data.has_approval:
                                draft_data.is_pending = True
                                draft_data.save()

                            draft_data.data_answer.filter(
                                question__required=True
                            ).delete()

                        if (not is_test and not form_data.is_pending):
                            form_data.save_to_file

                        if not form_data.is_draft:
                            submitter = None
                            if mobile_user.name and r % 2 == 0:
                                submitter = mobile_user.name
                            last_date = form_data.created
                            if last_date.tzinfo is None:
                                last_date = make_aware(last_date)
                            for child_form in f.children.all():
                                for m in range(monitoring):
                                    last_date += timedelta(days=1)
                                    ld_f1 = last_date.strftime('%Y-%m-%d')
                                    ld_f2 = last_date.strftime(
                                        '%a %b %d %Y %H:%M:%S'
                                    )
                                    curr_time = (
                                        f"{ld_f1} - {ld_f2} GMT+0700"
                                    )
                                    s_name = submitter \
                                        if m % 2 == 0 and submitter else None
                                    child_data = form_data.children.create(
                                        name=curr_time,
                                        uuid=form_data.uuid,
                                        administration=(
                                            form_data.administration
                                        ),
                                        geo=form_data.geo,
                                        form=child_form,
                                        created_by=user,
                                        is_pending=data_is_pending,
                                        is_draft=False,
                                        submitter=s_name,
                                    )
                                    child_data.created = last_date
                                    child_data.updated = last_date
                                    child_data.save()
                                    add_fake_answers(child_data)
                                    mark_as_dummy(child_data)
                                    form_monitoring_counts[f.name] += 1
                    index += 1
                for form_name, count in form_data_counts.items():
                    self.stdout.write(
                        f"Created {count} data entries for form {form_name}"
                    )
                for form_name, count in form_monitoring_counts.items():
                    if count > 0:
                        self.stdout.write(
                            f"Created {count} monitoring data entries "
                            f"for form {form_name}"
                        )
                for form_name, count in form_pending_counts.items():
                    if count > 0:
                        self.stdout.write(
                            f"Created {count} pending data entries "
                            f"for form {form_name}"
                        )
                for form_name, count in form_draft_counts.items():
                    if count > 0:
                        self.stdout.write(
                            f"Created {count} draft data entries "
                            f"for form {form_name}"
                        )
            refresh_materialized_data()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created {repeat} fake data entries'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error occurred: {str(e)}.'
                    'All changes have been rolled back.'
                )
            )
            raise
