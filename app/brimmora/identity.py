"""Identity provider stand-in: users, groups, tokens, and the group cache."""
import time

import jwt
from cachetools import TTLCache

from .config import settings
from .db import admin

# Cached group resolution. The TTL is the stated staleness window for a
# user who is removed from a group (case study: ACL drift).
_groups = TTLCache(maxsize=10_000, ttl=settings.group_cache_ttl_seconds)


def groups_for(user_id, live=False):
    """The user's groups. live=True bypasses the cache (used for restricted content)."""
    if not live and user_id in _groups:
        return _groups[user_id]
    with admin() as conn:
        rows = conn.execute(
            "SELECT group_name FROM group_members WHERE user_id = %s ORDER BY group_name",
            (user_id,)).fetchall()
    groups = [r[0] for r in rows]
    _groups[user_id] = groups
    return groups


def user_exists(user_id):
    with admin() as conn:
        return conn.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,)).fetchone() is not None


def issue_token(user_id, hours=8):
    claims = {"sub": user_id, "exp": int(time.time()) + hours * 3600}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def verify_token(token):
    """Returns the user id. Groups are never read from the token; they are resolved server-side."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"]
