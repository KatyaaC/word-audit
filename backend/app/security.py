"""Request actor resolution from HTTP headers. Compatible with a JWT-backed replacement."""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException


@dataclass
class Actor:
    user: str
    role: str  # creator | reviewer | approver | brand_manager | admin


def get_actor(x_user: str = Header(default="anonymous"), x_role: str = Header(default="creator")) -> Actor:
    return Actor(user=x_user, role=x_role.lower())


def require(*roles: str):
    def dep(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role != "admin" and actor.role not in roles:
            raise HTTPException(403, f"Role '{actor.role}' cannot do this; needs one of {sorted(roles)}")
        return actor

    return dep
