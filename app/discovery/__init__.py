"""Device Discovery for LabLink Platform.

Provides intelligent device discovery across TCP, serial, USB,
and network transports with fingerprinting, protocol detection,
and driver recommendation.
"""

from app.discovery.base import DiscoveredDevice, DiscoveryConfig, DiscoveryMethod
from app.discovery.engine import DeviceDiscoveryEngine
from app.discovery.fingerprint import DeviceFingerprint, FingerprintResult
from app.discovery.recommender import DriverRecommendation, DriverRecommender

__all__ = [
    "DeviceDiscoveryEngine",
    "DeviceFingerprint",
    "DiscoveredDevice",
    "DiscoveryConfig",
    "DiscoveryMethod",
    "DriverRecommendation",
    "DriverRecommender",
    "FingerprintResult",
]
