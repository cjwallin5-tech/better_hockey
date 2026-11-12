import unittest
from unittest import mock

import auth
import config
import mail


class Throttle(unittest.TestCase):
    def setUp(self):
        auth._RESETS.clear()

    def test_five_requests_an_hour_then_blocked_per_key(self):
        keys = ("e:a@b.c", "ip:1.2.3.4")
        self.assertEqual([auth._reset_throttled(*keys) for _ in range(auth.RESET_LIMIT)], [False] * auth.RESET_LIMIT)
        self.assertTrue(auth._reset_throttled(*keys))

    def test_other_addresses_and_clients_are_not_blocked_by_one_address(self):
        for _ in range(auth.RESET_LIMIT + 1):
            auth._reset_throttled("e:a@b.c", "ip:1.1.1.1")
        self.assertFalse(auth._reset_throttled("e:x@y.z", "ip:2.2.2.2"))

    def test_the_block_lifts_after_an_hour(self):
        with mock.patch("auth.time.time", return_value=1000.0):
            for _ in range(auth.RESET_LIMIT + 1):
                auth._reset_throttled("e:a@b.c")
        with mock.patch("auth.time.time", return_value=1000.0 + 3601):
            self.assertFalse(auth._reset_throttled("e:a@b.c"))


class Tokens(unittest.TestCase):
    def test_only_a_hash_is_kept_and_it_is_stable(self):
        h = auth._token_hash("abc")
        self.assertEqual(h, auth._token_hash("abc"))
        self.assertNotEqual(h, auth._token_hash("abd"))
        self.assertNotIn("abc", h)
        self.assertEqual(len(h), 64)


class ResetEmail(unittest.TestCase):
    LINK = "http://localhost:5173/reset-password?token=TOKEN123"

    def test_without_a_mail_server_the_link_goes_to_the_log_and_nothing_is_sent(self):
        with mock.patch.object(config, "SMTP_HOST", None), mock.patch.object(mail, "send_with_retry") as send:
            with self.assertLogs("uvicorn.error", level="WARNING") as logs:
                auth._send_reset_email("a@b.c", self.LINK)
        send.assert_not_called()
        self.assertIn(self.LINK, logs.output[0])

    def test_the_email_has_the_link_the_lifetime_and_a_not_you_line(self):
        with mock.patch.object(config, "SMTP_HOST", "smtp.example.test"), \
                mock.patch.object(mail, "send_with_retry", return_value=True) as send:
            auth._send_reset_email("a@b.c", self.LINK)
        (to, subject, body), kwargs = send.call_args
        self.assertEqual((to, subject), ("a@b.c", "Reset your Faceoff password"))
        self.assertIn(self.LINK, body)
        self.assertIn(f"{auth.RESET_MINUTES} minutes", body)
        self.assertIn("ignore this email", body)
        self.assertEqual(kwargs["attempts"], auth.RESET_SEND_ATTEMPTS)

    def test_a_send_that_never_works_is_logged_without_the_link(self):
        with mock.patch.object(config, "SMTP_HOST", "smtp.example.test"), \
                mock.patch.object(mail, "send_with_retry", return_value=False):
            with self.assertLogs("uvicorn.error", level="ERROR") as logs:
                auth._send_reset_email("a@b.c", self.LINK)
        self.assertIn("a@b.c", logs.output[0])
        self.assertNotIn("TOKEN123", logs.output[0])


class SendRetry(unittest.TestCase):
    def test_retries_with_growing_waits_until_it_goes_through(self):
        waits = []
        with mock.patch.object(mail, "send", side_effect=[False, False, True]) as send:
            self.assertTrue(mail.send_with_retry("a@b.c", "s", "b", attempts=3, wait=5, sleep=waits.append))
        self.assertEqual((send.call_count, waits), (3, [5, 10]))

    def test_false_after_the_last_try_with_no_trailing_wait(self):
        waits = []
        with mock.patch.object(mail, "send", return_value=False) as send:
            self.assertFalse(mail.send_with_retry("a@b.c", "s", "b", attempts=2, wait=5, sleep=waits.append))
        self.assertEqual((send.call_count, waits), (2, [5]))

    def test_no_retry_once_accepted(self):
        with mock.patch.object(mail, "send", return_value=True) as send:
            self.assertTrue(mail.send_with_retry("a@b.c", "s", "b", sleep=lambda s: self.fail("should not wait")))
        self.assertEqual(send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
