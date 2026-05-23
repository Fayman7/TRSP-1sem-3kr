from typing import Literal

Role = Literal["admin", "user", "guest"]

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    "admin": {"create", "read", "update", "delete"},
    "user": {"read", "update"},
    "guest": {"read"},
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role)  # type: ignore[arg-type]
    return permission in permissions if permissions else False
