import re

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser, Tenant


# Reuses the backend from the send-logging tests rather than defining a
# second one: there is only one way for a provider to fail here, and two
# copies of it would drift.
EXPLODING_BACKEND = (
    "api.v1.v1_users.tests.tests_email_send_logging.ExplodingBackend"
)


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", WEBDOMAIN="https://app.com"
)
class SecondWorkspaceActivationEmailTestCase(TestCase):
    """Registering a second workspace with an already-registered address.

    This is the reported scenario: an account that already exists on one
    workspace registers another, and the activation email never arrives,
    leaving the second workspace impossible to activate.

    Unlike the other registration tests, these do not mock ``send_email``.
    Mocking it asserts that the view *asked* for an email, which was never
    in doubt -- the reported failure was that asking is not sending. These
    go through the real helper and inspect what the mail backend received.
    """

    email = "founder@acme.org"
    password = "Secret#Pass123"

    def register(self, subdomain):
        return self.client.post(
            "/api/v1/register",
            {
                "email": self.email,
                "password": self.password,
                "subdomain": subdomain,
            },
            content_type="application/json",
            HTTP_HOST="app.com",
        )

    def activation_link(self, message):
        """Pull the activation URL out of the HTML part of a sent email."""
        html = message.alternatives[0][0]
        found = re.search(r"https://[\w.-]+/activate/[\w:\-]+", html)
        self.assertIsNotNone(found, "no activation link in the email body")
        return found.group(0)

    def test_second_workspace_gets_its_own_activation_email(self):
        self.assertEqual(self.register("acme").status_code, 200)
        self.assertEqual(self.register("beta").status_code, 200)

        # Two accounts, because email is unique per tenant rather than
        # globally -- which is what makes this scenario legal at all.
        self.assertEqual(
            SystemUser.objects.filter(email=self.email).count(), 2
        )

        # ...and two emails actually handed to the mail backend. Before
        # this was tested, a send that failed produced the same 200 and
        # the same "Check your email" as one that succeeded.
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertEqual(message.to, [self.email])

        # The second link must point at the second workspace. Sending the
        # registrant back to acme would activate the wrong account and
        # leave beta permanently unactivatable, which is the symptom that
        # was reported.
        self.assertTrue(
            self.activation_link(mail.outbox[0]).startswith(
                "https://acme.app.com/activate/"
            ),
            self.activation_link(mail.outbox[0]),
        )
        self.assertTrue(
            self.activation_link(mail.outbox[1]).startswith(
                "https://beta.app.com/activate/"
            ),
            self.activation_link(mail.outbox[1]),
        )

    def test_each_activation_link_activates_only_its_own_account(self):
        self.register("acme")
        self.register("beta")
        acme_user = SystemUser.objects.get(
            email=self.email, tenant__subdomain="acme"
        )
        beta_user = SystemUser.objects.get(
            email=self.email, tenant__subdomain="beta"
        )
        self.assertFalse(acme_user.is_active)
        self.assertFalse(beta_user.is_active)

        token = self.activation_link(mail.outbox[1]).rsplit("/", 1)[1]
        response = self.client.post(
            "/api/v1/register/activate",
            {"token": token},
            content_type="application/json",
            HTTP_HOST="beta.app.com",
        )
        self.assertEqual(response.status_code, 200)

        acme_user.refresh_from_db()
        beta_user.refresh_from_db()
        self.assertTrue(beta_user.is_active)
        # The two links carry different signed primary keys. If they did
        # not, following the second would activate the first workspace's
        # account and the registrant would still be locked out of beta.
        self.assertFalse(acme_user.is_active)

    @override_settings(EMAIL_BACKEND=EXPLODING_BACKEND)
    def test_registration_reports_success_but_logs_when_the_email_fails(self):
        with self.assertLogs("utils.email_helper", level="ERROR") as logs:
            response = self.register("acme")

        # Still a 200: the tenant and the account were created and the
        # transaction committed, so failing the request now would be a lie
        # in the other direction. The registrant recovers with resend.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Tenant.objects.filter(subdomain="acme").exists())
        self.assertFalse(
            SystemUser.objects.get(email=self.email).is_active
        )

        # The part that was missing when this was reported: the failure is
        # now on the record, naming the email type and the recipient.
        output = "\n".join(logs.output)
        self.assertIn("failed to send user_activation email", output)
        self.assertIn(self.email, output)
