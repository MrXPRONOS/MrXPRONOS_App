"""Offline test for read-only Bluesky diagnostic's secret-safe logging."""
import contextlib
import io
import unittest
from scripts import bluesky_readonly_diagnostic as diagnostic


class ReadOnlyDiagnosticTests(unittest.TestCase):
    def test_missing_credentials_no_network(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = diagnostic.audit("", "not-a-secret")
        self.assertEqual(result, 3)
        self.assertNotIn("not-a-secret", output.getvalue())

    def test_type_error_only_reports_class_and_frame(self):
        output = io.StringIO()
        secret = "NEVER_PRINT_ME"
        def fail():
            raise TypeError(secret)
        with contextlib.redirect_stdout(output):
            with self.assertRaises(TypeError):
                diagnostic.call_stage("Client_login", fail)
        reported = output.getvalue()
        self.assertIn("stage=Client_login", reported)
        self.assertIn("type=TypeError", reported)
        self.assertNotIn(secret, reported)


if __name__ == "__main__":
    unittest.main()
