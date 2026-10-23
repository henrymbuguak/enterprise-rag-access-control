"""Embedding upgrade without rebuilding in place: build a new index, then swap the alias.

python -m brimmora.upgrade build v2 | swap v2 | swap v1   (rollback)
"""
import sys

from . import ingest, search
from .config import settings


def build(version):
    if version != settings.embedding_version:
        sys.exit(f"set EMBEDDING_VERSION={version} and the new EMBEDDING_MODEL in .env first")
    name = search.create_index(version)
    ingest.full_sync(index=name)
    ingest.validate(index=name)
    print(f"built {name}; the alias still points at the old index")


def swap(version):
    client, alias = search.os_client(), settings.index_alias
    target = f"{alias}-{version}"
    current = list(client.indices.get_alias(name=alias).keys())
    actions = [{"remove": {"index": i, "alias": alias}} for i in current]
    client.indices.update_aliases(body={"actions": actions + [{"add": {"index": target, "alias": alias}}]})
    print(f"{alias}: {current} -> {target} (old index kept for rollback)")


if __name__ == "__main__":
    {"build": build, "swap": swap}[sys.argv[1]](sys.argv[2])
