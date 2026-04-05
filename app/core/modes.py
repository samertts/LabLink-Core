from __future__ import annotations

from enum import Enum


class CommunicationMode(str, Enum):
    LOCAL_ONLY = "local_only"
    HYBRID = "hybrid"
    CLOUD_ONLY = "cloud_only"
