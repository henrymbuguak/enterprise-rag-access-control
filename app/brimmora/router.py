"""Intent router: rag (documents), sql (exact records), or mixed (records, then document text)."""
import datetime as dt
import json

from .llm import chat
from .metrics import ROUTES
from .tools import TOOLS

SYSTEM = """You route questions for Brimmora's enterprise assistant. Reply with JSON only:
{"route": "rag" | "sql" | "mixed", "tool": "<tool name or null>", "args": {}, "confidence": 0.0}

Routes:
- rag: answered from documents: procedures, manuals, incident reports, service bulletins, policies,
  design notes, or the wording of one specific contract.
- sql: answered exactly from records: lists, statuses, schedules, amounts. Pick one tool and its args.
- mixed: needs records first and then document text about them, such as the clauses or terms
  of the active contracts with a supplier. Always use get_active_contracts.

Tools:
<<TOOLS>>

The current quarter is <<CURRENT>>; "last quarter" means <<PREVIOUS>>.

Examples:
Q: Which supplier contracts are currently active?
A: {"route": "sql", "tool": "get_active_contracts", "args": {"supplier": null}, "confidence": 0.95}
Q: What does the lockout-tagout procedure require?
A: {"route": "rag", "tool": null, "args": {}, "confidence": 0.95}
Q: What are the termination terms in our active contracts with Acme?
A: {"route": "mixed", "tool": "get_active_contracts", "args": {"supplier": "Acme"}, "confidence": 0.9}"""


def _quarters(today=None):
    today = today or dt.date.today()
    q = (today.month - 1) // 3 + 1
    previous = f"{today.year}-Q{q - 1}" if q > 1 else f"{today.year - 1}-Q4"
    return f"{today.year}-Q{q}", previous


def _prompt():
    tools = "\n".join(
        f"- {t['name']}({', '.join(f'{k}: {v}' for k, v in t['params'].items())}): {t['description']}"
        for t in TOOLS.values())
    current, previous = _quarters()
    return SYSTEM.replace("<<TOOLS>>", tools).replace("<<CURRENT>>", current).replace("<<PREVIOUS>>", previous)


def route(question):
    raw = chat([{"role": "system", "content": _prompt()}, {"role": "user", "content": question}],
               purpose="router", json_mode=True)
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {}
    choice, tool, args = plan.get("route"), plan.get("tool"), plan.get("args") or {}
    try:
        confidence = float(plan.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if choice not in ("rag", "sql", "mixed"):
        choice, confidence = "rag", 0.0              # unknown → documents, flagged as low confidence
    if choice == "mixed":
        tool = "get_active_contracts"
    if choice == "sql" and tool not in TOOLS:
        choice, tool, confidence = "rag", None, 0.0
    if choice == "rag" and tool not in TOOLS:
        tool = None
    ROUTES.labels(choice).inc()
    return {"route": choice, "tool": tool, "args": args if isinstance(args, dict) else {},
            "confidence": confidence}
