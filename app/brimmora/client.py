"""Small HTTP client for the answer service, used by the CLI, checks, and evaluation."""
import httpx

from .config import settings


def token(user):
    r = httpx.get(f"{settings.api_url}/dev/token", params={"user": user}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def ask(user, question):
    r = httpx.post(f"{settings.api_url}/ask", json={"question": question},
                   headers={"Authorization": f"Bearer {token(user)}"}, timeout=600)
    r.raise_for_status()
    return r.json()


def audit(request_id):
    r = httpx.get(f"{settings.api_url}/audit/{request_id}", timeout=30)
    r.raise_for_status()
    return r.json()
