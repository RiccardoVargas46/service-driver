# Test service_driver.core against a synthetic services file.
import os
import tempfile
import unittest

from service_driver.core import ServiceResolver, ResolveError, ServiceRecord


# A representative slice of /etc/services exercising the tricky paths:
#   - comment-only line
#   - blank line
#   - inline comment
#   - aliases (ssh also known as mosh?)
#   - case-insensitive lookups
#   - multiple protocols for one name (domain tcp/udp)
#   - an out-of-range port that should be rejected
SAMPLE = """# Sample services file for testing
# comment-only line

ssh             22/tcp          # SSH remote login
telnet          23/tcp
ftp-data        20/tcp
domain          53/tcp          # DNS
domain          53/udp
http            80/tcp          www www-http   # World Wide Web
bad             99999/tcp       # out of range, should be skipped
"""


class TestServiceResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = os.path.join(self.tmpdir.name, "services")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE)
        self.resolver = ServiceResolver(path=self.path)

    def test_resolves_ssh_tcp(self) -> None:
        rec = self.resolver.resolve("ssh", "tcp")
        self.assertEqual(rec.name, "ssh")
        self.assertEqual(rec.port, 22)
        self.assertEqual(rec.protocol, "tcp")

    def test_resolves_case_insensitive_name_and_proto(self) -> None:
        rec = self.resolver.resolve("SSH", "TCP")
        self.assertEqual(rec.port, 22)
        self.assertEqual(rec.protocol, "tcp")
        self.assertEqual(rec.name, "ssh")

    def test_resolves_domain_tcp_and_udp_distinct(self) -> None:
        tcp = self.resolver.resolve("domain", "tcp")
        udp = self.resolver.resolve("domain", "udp")
        self.assertEqual(tcp.port, 53)
        self.assertEqual(udp.port, 53)
        self.assertNotEqual((tcp.name, tcp.protocol), (udp.name, udp.protocol))

    def test_resolves_alias_for_http(self) -> None:
        # "www" is an alias for http on the same line.
        rec = self.resolver.resolve("www", "tcp")
        self.assertEqual(rec.port, 80)
        self.assertEqual(rec.name, "http")

    def test_resolves_second_alias(self) -> None:
        rec = self.resolver.resolve("www-http", "tcp")
        self.assertEqual(rec.port, 80)

    def test_resolve_port_returns_int(self) -> None:
        port = self.resolver.resolve_port("ssh", "tcp")
        self.assertIsInstance(port, int)
        self.assertEqual(port, 22)

    def test_resolve_unknown_raises(self) -> None:
        with self.assertRaises(ResolveError):
            self.resolver.resolve("nosuchservice", "tcp")

    def test_resolve_unknown_protocol_raises(self) -> None:
        with self.assertRaises(ResolveError):
            self.resolver.resolve("ssh", "udp")

    def test_out_of_range_port_is_ignored(self) -> None:
        with self.assertRaises(ResolveError):
            self.resolver.resolve("bad", "tcp")

    def test_has_service_true_for_canonical(self) -> None:
        self.assertTrue(self.resolver.has_service("ssh", "tcp"))

    def test_has_service_true_for_alias(self) -> None:
        self.assertTrue(self.resolver.has_service("www", "tcp"))

    def test_has_service_false_for_missing(self) -> None:
        self.assertFalse(self.resolver.has_service("nosuch", "tcp"))
        self.assertFalse(self.resolver.has_service("ssh", "udp"))

    def test_path_property_returns_loaded_file(self) -> None:
        self.assertEqual(self.resolver.path, self.path)

    def test_resolve_returns_frozen_service_record(self) -> None:
        rec = self.resolver.resolve("ssh", "tcp")
        self.assertIsInstance(rec, ServiceRecord)
        # Frozen dataclass: attribute assignment should raise.
        with self.assertRaises(Exception):
            rec.port = 999  # type: ignore[misc]

    def test_first_canonical_name_wins_on_duplicate(self) -> None:
        # If a duplicate (name, proto) appears, the first entry is kept.
        # We simulate by adding a second ssh line with a different port.
        dup = "ssh 222/tcp\n"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(dup)
        new_resolver = ServiceResolver(path=self.path)
        rec = new_resolver.resolve("ssh", "tcp")
        self.assertEqual(rec.port, 22)


if __name__ == "__main__":
    unittest.main()
