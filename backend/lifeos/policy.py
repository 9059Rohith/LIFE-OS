"""Typed deterministic policy. No model can add tools or alter risk decisions."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import math


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"


@dataclass(frozen=True)
class ActionPolicy:
    risk: Risk
    requires_approval: bool


ALLOWED: dict[str, frozenset[str]] = {
    "calendar": frozenset({"update"}),
    "gmail": frozenset({"send"}),
    "discord": frozenset({"send"}),
    "whatsapp": frozenset({"send"}),
    "drive": frozenset({"read"}),
}


def classify(application: str, action_type: str) -> ActionPolicy:
    if action_type not in ALLOWED.get(application, frozenset()):
        raise ValueError("Unknown application or action type is denied")
    readonly = action_type == "read"
    return ActionPolicy(Risk.LOW if readonly else Risk.MEDIUM, not readonly)


def approval_valid(claims: Mapping[str, object], version: int, arguments_hash: str, now: float) -> bool:
    expires = claims.get("expires")
    if not isinstance(expires, (int, float)) or isinstance(expires, bool) or not math.isfinite(expires):
        return False
    return claims.get("version") == version and claims.get("hash") == arguments_hash and expires > now
