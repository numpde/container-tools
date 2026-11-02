"""Preserve DNS failure causes without disclosing private request data."""

from tools.container_guard import require_container

require_container()

import unittest
from unittest.mock import patch

from tools import bound_http_proxy

# Adapted from provider proxy adversarial tests at revision b170571.


class ProxyResolutionTests(unittest.TestCase):
    def test_dns_owner_keeps_safe_reason_and_original_query_failure_separate(self):
        primary = TimeoutError("PRIVATE_RESOLVER")
        with (
            patch.object(bound_http_proxy, "_dns_servers", return_value=("192.0.2.53",)),
            patch.object(bound_http_proxy, "_query_ipv4", side_effect=primary),
            patch.object(bound_http_proxy.time, "monotonic", return_value=0),
            self.assertRaises(bound_http_proxy.ProxyResolutionFailed) as caught,
        ):
            bound_http_proxy.resolve_ipv4_bound("PRIVATE_HOST", "eth0", deadline=30)
        self.assertEqual(caught.exception.failures, (primary,))
        self.assertIn("configured DNS queries failed", str(caught.exception))
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_dns_deadline_keeps_prior_query_cause_without_starting_next_resolver(self):
        primary = OSError("PRIVATE_QUERY")
        clock = [0]

        def expire(*_args, **_kwargs):
            clock[0] = 31
            raise primary

        with (
            patch.object(bound_http_proxy, "_dns_servers", return_value=("192.0.2.53", "192.0.2.54")),
            patch.object(bound_http_proxy, "_query_ipv4", side_effect=expire) as query,
            patch.object(bound_http_proxy.time, "monotonic", side_effect=lambda: clock[0]),
            self.assertRaises(bound_http_proxy.ProxyResolutionFailed) as caught,
        ):
            bound_http_proxy.resolve_ipv4_bound("PRIVATE_HOST", "eth0", deadline=30)
        self.assertIsInstance(caught.exception, TimeoutError)
        self.assertIs(caught.exception.failures[0], primary)
        self.assertIsInstance(caught.exception.failures[1], TimeoutError)
        self.assertIn("shared DNS deadline elapsed", str(caught.exception))
        self.assertNotIn("PRIVATE", str(caught.exception))
        query.assert_called_once_with("private_host", "192.0.2.53", "eth0", deadline=30)
