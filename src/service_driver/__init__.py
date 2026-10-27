# service-driver: resolve IANA service names to ports and protocols.
"""
Public API for the service_driver package.
"""

from service_driver.core import ServiceResolver, ResolveError

__all__ = ["ServiceResolver", "ResolveError"]
