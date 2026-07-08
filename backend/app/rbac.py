from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import User


ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_CONTENT_OPERATOR = "content_operator"
VALID_ROLES = {ROLE_USER, ROLE_ADMIN, ROLE_CONTENT_OPERATOR}


class AdminPhoneSettings(Protocol):
    @property
    def admin_phone_set(self) -> set[str]:
        ...


@dataclass(frozen=True)
class AdminAccessDecision:
    allowed: bool
    user_role: str
    access_source: str | None
    reason: str | None


def get_user_role(user: User | None) -> str:
    role = getattr(user, "role", None)
    if isinstance(role, str) and role in VALID_ROLES:
        return role
    return ROLE_USER


def has_role(user: User | None, role: str) -> bool:
    return get_user_role(user) == role


def is_admin_user(user: User | None, settings: AdminPhoneSettings) -> bool:
    return admin_access_decision(user, settings).allowed


def admin_access_decision(user: User | None, settings: AdminPhoneSettings) -> AdminAccessDecision:
    role = get_user_role(user)
    if role == ROLE_ADMIN:
        return AdminAccessDecision(allowed=True, user_role=role, access_source="role", reason=None)
    if user and user.phone and user.phone in settings.admin_phone_set:
        return AdminAccessDecision(allowed=True, user_role=role, access_source="admin_phone_fallback", reason=None)
    if role == ROLE_CONTENT_OPERATOR:
        reason = "content_operator_not_admin"
    else:
        reason = "rbac_denied"
    return AdminAccessDecision(allowed=False, user_role=role, access_source=None, reason=reason)
