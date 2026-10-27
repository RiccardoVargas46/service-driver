# service-driver

Resolves IANA service names (like `ssh`, `http`, `domain`) to their canonical port numbers and protocols using the built-in OS services file.

```python
from service_driver import ServiceResolver, ResolveError

resolver = ServiceResolver()

# Get the full record
record = resolver.resolve("ssh", "tcp")
print(record.name, record.port, record.protocol)  # ssh 22 tcp

# Get just the port
port = resolver.resolve_port("http", "tcp")
print(port)  # 80

# Check existence without raising
if resolver.has_service("domain", "udp"):
    print("found")
```

## Why

Networking code that hardcodes port numbers (`22`, `53`, `80`) loses the connection between the number and the service it represents. This library recovers that link by reading the IANA services file (`/etc/services` on Unix, `C:\\Windows\\System32\\drivers\\etc\\services` on Windows) that ships with the operating system. The trade-off is portability for freshness: the data is whatever the local OS ships, so a container stripped of `/etc/services` will fail at construction time rather than silently returning stale defaults.

## Edge cases

- Names and protocols are matched case-insensitively. `SSH`/`tcp` and `ssh`/`TCP` resolve identically.
- Aliases listed on the same line (e.g., `http 80/tcp www www-http`) resolve to the canonical record. The first canonical name seen for a given `(name, protocol)` pair wins, matching the convention of the services file.
- Ports outside the valid range (0-65535) in the services file are silently skipped to avoid poisoning the index.
- If the services file cannot be found, construction raises `FileNotFoundError`. Construct with `ServiceResolver(path=...)` to point at an explicit file in tests or unusual environments.
