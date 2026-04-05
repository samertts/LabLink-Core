from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.normalizer import NormalizedResult


@dataclass(slots=True)
class RouteDecision:
    target: str
    reason: str


class SmartRoutingEngine:
    """Decides where outbound results should go (gula/offline/both)."""

    def __init__(self) -> None:
        self.device_policies: dict[str, str] = {}

    def set_policy(self, device_id: str, policy: str) -> None:
        self.device_policies[device_id] = policy

    def decide(self, *, device_id: str, results: list[NormalizedResult]) -> RouteDecision:
        policy = self.device_policies.get(device_id, "gula")
        if policy in {"gula", "offline", "both"}:
            return RouteDecision(target=policy, reason="device_policy")
        return RouteDecision(target="gula", reason="default")
