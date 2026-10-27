# Resolve IANA service names to (port, protocol) tuples from the OS services file.
"""
Core resolver: reads the OS-provided services file and maps service names to
their canonical port and protocol.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


# The OS services file lists one record per line. We only need the name,
# port/protocol, and (optionally) any aliases that follow on the same line.
# Format: "name  port/proto  [aliases...]  # comment"
_RECORD_RE = re.compile(
    r"""
    \s*
    (?P<name>[^\s/#]+)          # service name, stop at whitespace, /, or #
    \s+
    (?P<port>\d+)               # port number, digits only
    /
    (?P<proto>[^\s/#]+)         # protocol, stop at whitespace, /, or #
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class ServiceRecord:
    """A single resolved service entry."""

    name: str
    port: int
    protocol: str


class ResolveError(LookupError):
    """Raised when a (service, protocol) pair cannot be resolved."""


class ServiceResolver:
    """Resolve IANA service names to ports and protocols.

    The resolver reads the built-in services file once at construction and
    builds an index keyed by (name_lower, protocol_lower). Loading up-front
    is O(n) in the file size (typically a few hundred lines) and makes every
    lookup a plain dict access, which is the read-heavy pattern this tool
    exists for. If you need to refresh, construct a new resolver.
    """

    DEFAULT_PATHS = (
        "/etc/services",
        os.path.join(os.environ.get("SystemRoot", r"C:\\WINDOWS"), "System32", "drivers", "etc", "services"),
    )

    def __init__(self, path: str | None = None) -> None:
        self._path = path
        self._entries: dict[tuple[str, str], ServiceRecord] = {}
        self._aliases: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self._load()

    @property
    def path(self) -> str:
        """Return the services file that was actually read."""
        assert self._path is not None  # set by _load before this is usable
        return self._path

    def resolve(self, name: str, protocol: str) -> ServiceRecord:
        """Resolve a service name and protocol to a ServiceRecord.

        Raises ResolveError if no matching entry exists.
        """
        key = (name.lower(), protocol.lower())
        entry = self._entries.get(key)
        if entry is not None:
            return entry
        # Check if name is an alias; if so, map to the canonical name.
        if key in self._aliases:
            # Return the first canonical entry that this alias maps to.
            for canon_key in self._aliases[key]:
                entry = self._entries.get(canon_key)
                if entry is not None:
                    return entry
        raise ResolveError(f"No entry for service '{name}' with protocol '{protocol}'")

    def resolve_port(self, name: str, protocol: str) -> int:
        """Return only the port number for a service and protocol."""
        return self.resolve(name, protocol).port

    def has_service(self, name: str, protocol: str) -> bool:
        """Return True if (name, protocol) is resolvable (including aliases)."""
        key = (name.lower(), protocol.lower())
        return key in self._entries or key in self._aliases

    def _load(self) -> None:
        path = self._find_file()
        self._path = path
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                self._parse_line(line)

    def _find_file(self) -> str:
        if self._path is not None:
            return self._path
        for candidate in self.DEFAULT_PATHS:
            if os.path.isfile(candidate):
                return candidate
        # Fall back to /etc/services even if it does not exist so the error
        # message points at a conventional location.
        return "/etc/services"

    def _parse_line(self, line: str) -> None:
        # Strip comments and surrounding whitespace; blank lines are ignored.
        stripped = self._strip_comment(line).strip()
        if not stripped:
            return
        m = _RECORD_RE.match(stripped)
        if m is None:
            return
        name = m.group("name")
        proto = m.group("proto")
        port_s = m.group("port")
        try:
            port = int(port_s)
        except ValueError:
            return
        if port < 0 or port > 65535:
            # Out-of-range ports in the services file are malformed; skip them
            # rather than poisoning the index with unusable values.
            return
        key = (name.lower(), proto.lower())
        record = ServiceRecord(name=name, port=port, protocol=proto)
        # First canonical name wins, matching the services-file convention
        # where the first occurrence is the official name and later lines
        # for the same port/proto pair are aliases.
        self._entries.setdefault(key, record)
        # Collect aliases: any tokens after port/proto on this line.
        rest = stripped[m.end():].strip()
        if rest:
            for alias in re.split(r"\s+", rest):
                # Split defensively handles any stray whitespace.
                alias_key = (alias.lower(), proto.lower())
                self._aliases.setdefault(alias_key, []).append(key)

    @staticmethod
    def _strip_comment(line: str) -> str:
        idx = line.find("#")
        if idx == -1:
            return line
        return line[:idx]
