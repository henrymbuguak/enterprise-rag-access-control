"""Curated structured tools. The model picks a tool and its arguments; it never writes SQL."""
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from .db import as_user

TOOLS = {t["name"]: t for t in json.loads(Path(__file__).with_name("tools.json").read_text())}


def _clean(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_tool(name, args, groups):
    """Runs a tool as the user: row-level security decides which rows come back."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ValueError(f"unknown tool: {name}")
    if tool["auth_mode"] != "user":
        raise PermissionError(f"tool {name} is not user-scoped")
    params = {p: (args or {}).get(p) for p in tool["params"]}
    with as_user(groups) as conn:
        cur = conn.execute(tool["sql"], params)
        columns = [c.name for c in cur.description]
        return [{c: _clean(v) for c, v in zip(columns, row)} for row in cur.fetchall()]
