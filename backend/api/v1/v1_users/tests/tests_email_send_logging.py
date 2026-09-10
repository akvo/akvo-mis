from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import SimpleTestCase
from django.test.utils import override_settings

from utils.email_helper import EmailTypes, send_email


class ExplodingBackend(BaseEmailBackend):
    """Fails the way a provider outage does: by raising out of ``send``."""

    def send_messages(self, email_messages):
        raise RuntimeError("provider refused the message")


# The activation email, because that is the one whose silent failure was
# reported: a registrant saw "Check your email" and no email ever came.
CONTEXT = {
    "send_to": ["registrant@example.com"],
    "button_url": "https://workspace.example.test/activate/sometoken",
}


class SendEmailReportingTestCase(SimpleTestCase):
    """``send_email`` must make the outcome of a send observable.

    It still never raises -- callers depend on that -- so the only way a
    failure can be distinguished from a success is the return value and the
    log record. Both are asserted here.
    """

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_returns_true_and_logs_when_the_backend_accepts(self):
        with self.assertLogs("utils.email_helper", level="INFO") as logs:
            sent = send_email(
                context=dict(CONTEXT), type=EmailTypes.user_activation
            )

        self.assertTrue(sent)
        output = "\n".join(logs.output)
        self.assertIn("sent user_activation email", output)

        # The logged handle must be the Message-ID the recipient's mail
        # server will actually see, otherwise it is useless for tracing a
        # message through that server's logs. Asserting they match is the
        # whole point of stamping the header ourselves.
        self.assertEqual(len(mail.outbox), 1)
        message_id = mail.outbox[0].extra_headers["Message-ID"]
        self.assertIn(message_id, output)

    @override_settings(EMAIL_BACKEND=f"{__name__}.ExplodingBackend")
    def test_returns_false_and_logs_traceback_when_the_backend_raises(self):
        with self.assertLogs("utils.email_helper", level="ERROR") as logs:
            sent = send_email(
                context=dict(CONTEXT), type=EmailTypes.user_activation
            )

        self.assertFalse(sent)
        output = "\n".join(logs.output)
        # The message type and the recipient, so a log reader knows which
        # email died without correlating against anything else...
        self.assertIn("failed to send user_activation email", output)
        self.assertIn("registrant@example.com", output)
        # ...and the traceback, which is what `print(ex)` threw away.
        self.assertIn("RuntimeError: provider refused the message", output)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_preview_mode_still_returns_the_rendered_html(self):
        # The email_template view renders without sending and returns the
        # body, so the new boolean return must not have displaced it.
        body = send_email(
            context=dict(CONTEXT),
            type=EmailTypes.user_activation,
            send=False,
        )

        self.assertIsInstance(body, str)
        self.assertIn("activate/sometoken", body)
