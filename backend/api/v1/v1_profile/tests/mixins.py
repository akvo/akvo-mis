import typing
from io import BytesIO

import pandas as pd
from django.core.management.color import no_style
from django.db import connection
from django.test.client import Client
from faker import Faker
from rest_framework_simplejwt.tokens import RefreshToken
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    UserRole,
)
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_forms.models import UserForms, Forms
fake = Faker()

TENANT_PASSWORD = "Secret#Pass123"


class HasTestClientProtocol(typing.Protocol):
    @property
    def client(self) -> Client:
        ...


class ProfileTestHelperMixin:

    IS_SUPER_ADMIN = 0
    IS_ADMIN = 1
    IS_APPROVER = 2

    def create_user(
        self,
        email: str,
        role_level: int,
        password: str = 'password',
        administration: Administration = None,
        form: Forms = None,
    ) -> SystemUser:
        user = SystemUser.objects.filter(email=email).first()
        if user:
            return user
        profile = fake.profile()
        name = profile.get("name")
        name = name.split(" ")
        user = SystemUser.objects.create(
            email=email,
            first_name=name[0],
            last_name=name[1],
            is_superuser=role_level == self.IS_SUPER_ADMIN,
        )
        user.set_password(password)
        user.save()

        if not administration:
            if role_level == self.IS_SUPER_ADMIN:
                administration = Administration.objects.filter(
                    level__level=0
                ).order_by('?').first()
            else:
                administration = Administration.objects.filter(
                    level__level__gt=0
                ).order_by('?').first()
        if form:
            UserForms.objects.get_or_create(
                user=user,
                form=form
            )
        if role_level != self.IS_SUPER_ADMIN:
            role_name = "{0} {1}".format(
                administration.level.name,
                "Approver" if role_level == self.IS_APPROVER else "Admin"
            )
            role = Role.objects.filter(
                administration_level=administration.level,
                name=role_name,
            ).order_by('?').first()
            if role:
                UserRole.objects.get_or_create(
                    user=user,
                    role=role,
                    administration=administration
                )
        return user

    @staticmethod
    def reset_db_sequence(*models):
        """
        Auto fields are no longer incrementing after running create with
        explicit id parameter

        see: https://code.djangoproject.com/ticket/11423
        """
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), models)
        with connection.cursor() as cursor:
            for sql in sequence_sql:
                cursor.execute(sql)

    def get_auth_token(self: HasTestClientProtocol,
                       email: str,
                       password: str = 'password') -> str:
        response = self.client.post(
                '/api/v1/login',
                {'email': email, 'password': password},
                content_type='application/json')
        user = response.json()
        return user.get('token')


class TenantFixture(typing.NamedTuple):
    tenant: Tenant
    levels: typing.List[Levels]
    root: Administration
    admin: SystemUser


class TenantTestHelperMixin:
    """Builds the state a tenant is in once it has configured itself.

    Registration leaves exactly this behind — named levels, one root
    unit, one superadmin — and it is the starting point for everything
    the bulk-upload tests do. Four of them were assembling it by hand.
    """

    def create_tenant(
        self, subdomain: str, level_names: typing.List[str], root_name: str
    ) -> TenantFixture:
        tenant = Tenant.objects.create(subdomain=subdomain)
        levels = [
            Levels.objects.create(name=name, level=idx, tenant=tenant)
            for idx, name in enumerate(level_names)
        ]
        root = Administration.objects.create(
            parent=None, level=levels[0], name=root_name, tenant=tenant
        )
        admin = SystemUser.objects.create_superuser(
            email=f"admin@{subdomain}.org", password=TENANT_PASSWORD,
            first_name=subdomain.title(), last_name="Admin", tenant=tenant,
        )
        return TenantFixture(tenant, levels, root, admin)

    @staticmethod
    def bearer(user: SystemUser) -> dict:
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def administration_columns(levels: typing.List[Levels]) -> typing.List[str]:
    """The header row a generated administration template carries."""
    return [
        col
        for lvl in levels
        for col in [f"{lvl.id}|{lvl.name}", f"{lvl.id}|{lvl.name} Code"]
    ]


def write_administration_excel(levels, rows, path=None):
    """Build an upload file. Each row is one value per level, None blank.

    Returns the path when given one and an in-memory file otherwise —
    the validator takes either, but the job handler reads from ./tmp.
    """
    columns = administration_columns(levels)
    named = [
        {columns[idx * 2]: value for idx, value in enumerate(row)}
        for row in rows
    ]
    target = path or BytesIO()
    writer = pd.ExcelWriter(target, engine="xlsxwriter")
    pd.DataFrame(named, columns=columns).to_excel(
        writer, sheet_name="data", index=False
    )
    writer.save()
    return target
