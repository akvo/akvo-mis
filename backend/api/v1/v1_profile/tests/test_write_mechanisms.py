from rest_framework import serializers
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser, Tenant
from utils.tenant_scoped_model import TenantStampedSerializerMixin
from utils.custom_serializer_fields import TenantScopedPrimaryKeyRelatedField


class _StampSerializer(TenantStampedSerializerMixin,
                       serializers.ModelSerializer):
    class Meta:
        model = Forms
        fields = ["name"]


class _RefSerializer(serializers.Serializer):
    form = TenantScopedPrimaryKeyRelatedField(queryset=Forms.objects.all())


@override_settings(USE_TZ=False)
class WriteMechanismsTestCase(TestCase):
    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")
        self.acme_user = SystemUser.objects.create_superuser(
            email="a@acme.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=self.acme,
        )
        self.beta_form = Forms.objects.create(name="beta", tenant=self.beta)
        self.acme_form = Forms.objects.create(name="acme", tenant=self.acme)

    def test_stamp_sets_tenant_from_context_user(self):
        s = _StampSerializer(
            data={"name": "new"}, context={"user": self.acme_user}
        )
        s.is_valid(raise_exception=True)
        instance = s.save()
        self.assertEqual(instance.tenant, self.acme)

    def test_stamp_ignores_a_client_supplied_tenant(self):
        # Tenant is derived from the authenticated user, never bound from
        # the payload: a caller cannot plant a row in another tenant.
        s = _StampSerializer(
            data={"name": "new", "tenant": self.beta.id},
            context={"user": self.acme_user},
        )
        s.is_valid(raise_exception=True)
        self.assertEqual(s.save().tenant, self.acme)

    def test_stamp_resolves_user_from_request_context(self):
        class _Req:
            user = self.acme_user

        s = _StampSerializer(data={"name": "n"}, context={"request": _Req()})
        s.is_valid(raise_exception=True)
        self.assertEqual(s.save().tenant, self.acme)

    def test_scoped_field_accepts_own_tenant_object(self):
        s = _RefSerializer(
            data={"form": self.acme_form.id},
            context={"user": self.acme_user},
        )
        self.assertTrue(s.is_valid())

    def test_scoped_field_rejects_foreign_tenant_object(self):
        s = _RefSerializer(
            data={"form": self.beta_form.id},
            context={"user": self.acme_user},
        )
        self.assertFalse(s.is_valid())
        self.assertIn("form", s.errors)
