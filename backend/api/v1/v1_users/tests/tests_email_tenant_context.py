import html as html_lib
from django.core import mail
from django.test import TestCase, override_settings

from api.v1.v1_users.models import Tenant, SystemUser
from mis.settings import APP_NAME
from utils.email_helper import EmailTypes, email_context, send_email
from unittest import mock
from api.v1.v1_users.views import send_email_to_user

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

    def test_user_invite_email_content_and_structure(self):
        ctx = email_context(
            context={
                "tenant": self.tenant,
                "admin": "Dr. Alice",
                "button_url": "https://mohhs.app.com/login/abc123token",
            },
            type=EmailTypes.user_invite,
        )
        self.assertEqual(ctx["button_text"], "Set Up Your Password")
        self.assertEqual(
            ctx["button_url"], "https://mohhs.app.com/login/abc123token"
        )
        self.assertEqual(ctx["post_button_heading"], "What happens next?")
        self.assertEqual(len(ctx["post_button_steps"]), 3)
        self.assertIn(
            "Dr. Alice has invited you to join Ministry of Health & Human "
            "Services MIS.",
            ctx["body_paragraphs"],
        )
        self.assertIn(
            "Set up a secure password for your account.",
            ctx["post_button_steps"],
        )
        self.assertIn(
            "Sign in to Ministry of Health & Human Services MIS using your "
            "registered email address and password.",
            ctx["post_button_steps"],
        )
        self.assertTrue(bool(ctx["warning_note"]))
        self.assertIn(
            "We look forward to welcoming you to Ministry of Health & Human "
            "Services MIS.",
            ctx["sign_off"],
        )

    def test_user_invite_email_html_rendering(self):
        send_email(
            context={
                "send_to": ["doctor@mohhs.gov"],
                "tenant": self.tenant,
                "admin": "Dr. Alice",
                "button_url": "https://mohhs.app.com/login/abc123token",
            },
            type=EmailTypes.user_invite,
        )
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        html = sent.alternatives[0][0]
        decoded = html_lib.unescape(html)
        self.assertEqual(
            sent.subject,
            "Ministry of Health & Human Services MIS - New Invitation",
        )
        self.assertIn("Set Up Your Password", decoded)
        self.assertIn("What happens next?", decoded)
        self.assertIn("Dr. Alice has invited you to join", decoded)
        self.assertIn("Ministry of Health & Human Services MIS", decoded)
        self.assertIn("Set up a secure password for your account.", decoded)
        self.assertIn("If you weren't expecting this invitation", decoded)
        self.assertIn("We look forward to welcoming you", decoded)

    @mock.patch("api.v1.v1_users.views.send_email")
    def test_send_email_to_user_uses_request_actor_as_admin(
        self, mock_send_email
    ):
        mock_request = mock.Mock()
        mock_actor = mock.Mock()
        mock_actor.name = "Super Admin Bob"
        mock_request.user = mock_actor

        send_email_to_user(
            type=EmailTypes.user_invite,
            user=self.user,
            request=mock_request,
        )

        mock_send_email.assert_called_once()
        passed_context = mock_send_email.call_args.kwargs["context"]
        self.assertEqual(passed_context["admin"], "Super Admin Bob")
