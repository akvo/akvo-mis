import re

from django.core import mail
from django.test.utils import override_settings

from api.v1.v1_profile.models import Role
from api.v1.v1_users.models import Organisation, SystemUser
from utils.tenant_test_case import TenantIsolationTestCase


EXPLODING_BACKEND = (
    "api.v1.v1_users.tests.tests_email_send_logging.ExplodingBackend"
)


@override_settings(
    USE_TZ=False,
    BASE_DOMAIN="app.com",
    WEBDOMAIN="https://app.com",
    TEST_ENV=True,
)
class InviteEmailDeliveryTestCase(TenantIsolationTestCase):
    """Inviting a user, all the way through to what the mail backend got.

    The invite is the other half of the activation story: it is the only
    way a colleague gets into a workspace, and like activation it is a
    single emailed link with no alternative route in. An invite that is
    reported sent but never delivered leaves that person locked out with
    nothing on the record to explain why.

    Existing coverage calls ``send_email_to_user`` directly with
    ``send_email`` mocked. These go through the API endpoint an admin
    actually uses and read the message out of the outbox.
    """

    invitee = "colleague@example.org"

    def make_tenant(self, sub):
        # add-user resolves an organisation and a role, so the shared
        # fixture needs both before the endpoint will answer 201.
        tenant = super().make_tenant(sub)
        tenant["org"] = Organisation.objects.create(
            name=f"{sub}-org", tenant=tenant["tenant"]
        )
        tenant["role"] = Role.objects.create(
            name=f"{sub}-role", administration_level=tenant["level"]
        )
        return tenant

    def invite(self, workspace, email=None, inform_user=True, **overrides):
        payload = {
            "first_name": overrides.pop("first_name", "Invited"),
            "last_name": "Colleague",
            "email": email or self.invitee,
            "forms": [],
            "trained": False,
            "inform_user": inform_user,
            **overrides,
        }
        return self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_HOST=f"{workspace['tenant'].subdomain}.app.com",
            **self.auth(workspace["user"]),
        )

    def invite_link(self, message):
        html = message.alternatives[0][0]
        found = re.search(r"https://[\w.-]+/login/[\w:\-]+", html)
        self.assertIsNotNone(found, "no invite link in the email body")
        return found.group(0)

    def test_invite_sends_an_email_carrying_the_workspace_login_link(self):
        response = self.invite(self.a)
        self.assertEqual(response.status_code, 201)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.invitee])
        # The invitee's only way in is this link, and it is only valid on
        # the workspace that invited them.
        self.assertTrue(
            self.invite_link(mail.outbox[0]).startswith(
                "https://acme.app.com/login/"
            ),
            self.invite_link(mail.outbox[0]),
        )

    def test_no_email_is_sent_when_inform_user_is_false(self):
        response = self.invite(self.a, inform_user=False)
        self.assertEqual(response.status_code, 201)
        # The account exists either way; only the notification is optional.
        self.assertTrue(
            SystemUser.objects.filter(
                email=self.invitee, tenant=self.a["tenant"]
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_inviting_an_address_that_belongs_to_another_workspace(self):
        # The invitation-flow twin of the reported registration bug: this
        # address is already somebody in beta, and acme invites it too.
        existing = SystemUser.objects.create_user(
            email=self.invitee,
            password="Secret#Pass123",
            first_name="ExistingAtBeta",
            last_name="Colleague",
            tenant=self.b["tenant"],
        )

        response = self.invite(self.a, first_name="InvitedAtAcme")
        self.assertEqual(response.status_code, 201)

        self.assertEqual(len(mail.outbox), 1)
        link = self.invite_link(mail.outbox[0])
        self.assertTrue(link.startswith("https://acme.app.com/login/"), link)

        # And the signed key in it must name acme's new account, not the
        # beta one that happens to share the address. Resolving it through
        # the endpoint the frontend calls is what proves that: a link
        # carrying beta's key would greet the invitee by beta's name and
        # drop them into the wrong workspace.
        token = link.rsplit("/", 1)[1]
        verified = self.client.get(
            f"/api/v1/invitation/{token}",
            HTTP_HOST="acme.app.com",
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["name"], "InvitedAtAcme Colleague")

        invited = SystemUser.objects.get(
            email=self.invitee, tenant=self.a["tenant"]
        )
        self.assertNotEqual(invited.pk, existing.pk)

    @override_settings(EMAIL_BACKEND=EXPLODING_BACKEND)
    def test_invite_still_succeeds_but_logs_when_the_email_fails(self):
        with self.assertLogs("utils.email_helper", level="ERROR") as logs:
            response = self.invite(self.a)

        # The account was created before the notification was attempted,
        # so the request reports what actually happened.
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            SystemUser.objects.filter(
                email=self.invitee, tenant=self.a["tenant"]
            ).exists()
        )

        output = "\n".join(logs.output)
        self.assertIn("failed to send user_invite email", output)
        self.assertIn(self.invitee, output)
