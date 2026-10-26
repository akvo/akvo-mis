from django.core import mail
from django.test import TestCase, override_settings

from api.v1.v1_users.models import Tenant, SystemUser
from mis.settings import APP_NAME
from utils.email_helper import EmailTypes, email_context, send_email

LOCMEM = {
    "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
}


@override_settings(MAILERS=LOCMEM)
class EmailTenantNamingTestCase(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.tenant = Tenant.objects.create(
            subdomain="mohhs",
            name="Ministry of Health & Human Services",
        )
        self.user = SystemUser.objects.create(
            email="doctor@mohhs.gov",
            first_name="Dr.",
            last_name="Smith",
            tenant=self.tenant,
        )

    def test_send_email_prefixes_subject_with_tenant_mis_name(self):
        send_email(
            context={
                "send_to": ["doctor@mohhs.gov"],
                "tenant": self.tenant,
            },
            type=EmailTypes.user_register,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Ministry of Health & Human Services MIS - Registration",
        )

    def test_send_email_deduplicates_mis_suffix(self):
        tenant_mis = Tenant.objects.create(
            subdomain="kenya-mis",
            name="Kenya MIS",
        )
        send_email(
            context={
                "send_to": ["officer@kenya.gov"],
                "tenant": tenant_mis,
            },
            type=EmailTypes.user_register,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Kenya MIS - Registration",
        )

    def test_send_email_resolves_name_from_user_object(self):
        send_email(
            context={
                "send_to": ["doctor@mohhs.gov"],
                "user": self.user,
            },
            type=EmailTypes.user_register,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Ministry of Health & Human Services MIS - Registration",
        )

    def test_send_email_falls_back_to_app_name_when_no_tenant(self):
        send_email(
            context={
                "send_to": ["anon@example.com"],
            },
            type=EmailTypes.user_register,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f"{APP_NAME} - Registration",
        )

    def test_send_email_strips_crlf_to_prevent_header_injection(self):
        send_email(
            context={
                "send_to": ["doctor@mohhs.gov"],
                "name": "Malicious Name\r\nBcc: spammer@bad.org\r\n",
            },
            type=EmailTypes.user_register,
        )
        self.assertEqual(len(mail.outbox), 1)
        # CRLF must be removed so it cannot create additional email headers
        self.assertNotIn("\r", mail.outbox[0].subject)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertEqual(
            mail.outbox[0].subject,
            "Malicious NameBcc: spammer@bad.org MIS - Registration",
        )

    def test_email_context_sets_site_name_and_mis_name(self):
        ctx = email_context(
            context={"tenant": self.tenant},
            type=EmailTypes.user_register,
        )
        self.assertEqual(
            ctx["site_name"],
            "Ministry of Health & Human Services MIS",
        )
        self.assertEqual(
            ctx["mis_name"],
            "Ministry of Health & Human Services MIS",
        )

    def test_email_bodies_use_dynamic_mis_name(self):
        ctx_reg = email_context(
            context={"tenant": self.tenant},
            type=EmailTypes.user_register,
        )
        self.assertIn(
            "Ministry of Health & Human Services MIS", ctx_reg["body"]
        )

        ctx_act = email_context(
            context={"tenant": self.tenant},
            type=EmailTypes.user_activation,
        )
        self.assertIn(
            "Ministry of Health & Human Services MIS", ctx_act["body"]
        )

        ctx_upd = email_context(
            context={"tenant": self.tenant, "admin": "Admin User"},
            type=EmailTypes.user_update,
        )
        self.assertIn(
            "Ministry of Health & Human Services MIS", ctx_upd["body"]
        )

        ctx_err = email_context(
            context={"tenant": self.tenant},
            type=EmailTypes.upload_error,
        )
        self.assertIn(
            "Ministry of Health & Human Services MIS",
            ctx_err["info_text"],
        )
