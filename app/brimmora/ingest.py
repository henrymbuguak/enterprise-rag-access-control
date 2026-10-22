"""Ingestion shared by the scheduled path (Airflow) and the event path (consumer).

python -m brimmora.ingest init | sync | reconcile | validate
"""
import datetime as dt
import hashlib
import re
import sys

from opensearchpy import helpers

from . import search, sources
from .config import settings
from .constants import REQUIRED_FIELDS
from .db import admin

INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above|earlier) instructions"
    r"|disregard (all |the )?(previous|above)"
    r"|you are now"
    r"|reveal (your |the )?system prompt", re.I)
HIDDEN = re.compile(r"[​-‏⁠﻿]|color:\s*(?:#fff\b|#ffffff\b|white)", re.I)
OPTS = {"refresh": "true", "conflicts": "proceed"}


def admit(meta, text):
    """Fail closed. Returns a quarantine reason, or None when the document may be indexed."""
    tags = [t for t in meta.get("acl-tags", "").split(",") if t.strip()]
    if not tags or not meta.get("classification"):
        return "missing_security_metadata"
    if INJECTION.search(text) or HIDDEN.search(text):
        return "suspected_prompt_injection"
    return None


def title_of(text):
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")


def chunk(text, size=None, overlap=None):
    """Word windows with overlap; later chunks repeat the title for context."""
    size = size or settings.chunk_words
    overlap = settings.chunk_overlap if overlap is None else overlap
    words = text.split()
    if not words:
        return []
    title, step, pieces = title_of(text), max(1, size - overlap), []
    for start in range(0, len(words), step):
        body = " ".join(words[start:start + size])
        pieces.append(body if start == 0 or not title else f"{title}\n{body}")
        if start + size >= len(words):
            break
    return pieces


def _sql(statement, args):
    with admin() as conn:
        conn.execute(statement, args)


def quarantine(key, reason):
    _sql("INSERT INTO quarantine (object_key, reason) VALUES (%s, %s) "
         "ON CONFLICT (object_key) DO UPDATE SET reason = EXCLUDED.reason, detected_at = now()",
         (key, reason))


def release(key):
    _sql("DELETE FROM quarantine WHERE object_key = %s", (key,))


def _by_doc(key):
    return {"term": {"document_id": key}}


def remove_chunks(key, index=None):
    search.os_client().delete_by_query(index=index or settings.index_alias,
                                       body={"query": _by_doc(key)}, params=OPTS)


def tombstone(key, index=None):
    """Mark deleted first (instantly ineligible via the pre-filter), then remove."""
    idx = index or settings.index_alias
    search.os_client().update_by_query(index=idx, params=OPTS, body={
        "query": _by_doc(key),
        "script": {"lang": "painless", "source": "ctx._source.deletion_status = 'deleted'"}})
    remove_chunks(key, idx)
    release(key)


def _existing(key, index):
    res = search.os_client().search(index=index, body={
        "size": 1, "query": _by_doc(key),
        "_source": ["content_hash", "embedding_version", "chunking"]})
    hits = res["hits"]["hits"]
    return hits[0]["_source"] if hits else None


def index_document(key, index=None):
    """Brings the index in line with the source object's CURRENT state. Idempotent."""
    idx = index or settings.index_alias
    st = sources.stat(key)
    if st is None:
        tombstone(key, idx)
        return "deleted"
    meta, text = sources.metadata(st), sources.read_text(key)
    reason = admit(meta, text)
    if reason:
        remove_chunks(key, idx)
        quarantine(key, reason)
        return f"quarantined:{reason}"
    release(key)

    chunking = f"{settings.chunk_words}/{settings.chunk_overlap}"
    base = {
        "document_id": key,
        "source_uri": f"s3://{settings.bucket}/{key}",
        "source_version": st.etag,
        "content_hash": hashlib.sha256(text.encode()).hexdigest()[:12],
        "embedding_model": settings.embedding_model,
        "embedding_version": settings.embedding_version,
        "chunking": chunking,
        "last_modified": st.last_modified.isoformat(),
        "indexed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "region": settings.region,
        "tenant_id": settings.tenant_id,
        "data_classification": meta["classification"],
        "deletion_status": "active",
        "acl_tags": sorted({t.strip() for t in meta["acl-tags"].split(",") if t.strip()}),
        "doc_type": meta.get("doc-type", "document"),
        "contract_id": meta.get("contract-id"),
        "title": title_of(text),
    }

    prev = _existing(key, idx)
    if prev and (prev.get("content_hash"), prev.get("embedding_version"), prev.get("chunking")) == \
            (base["content_hash"], settings.embedding_version, chunking):
        # Same content and pipeline: a metadata-only change such as an ACL update. No re-embedding.
        fields = {k: v for k, v in base.items() if k != "document_id"}
        search.os_client().update_by_query(index=idx, params=OPTS, body={
            "query": _by_doc(key),
            "script": {"lang": "painless", "params": {"f": fields},
                       "source": "for (e in params.f.entrySet()) { ctx._source[e.getKey()] = e.getValue(); }"}})
        return "metadata-updated"

    pieces = chunk(text)
    vectors = search.embed_passages(pieces)
    remove_chunks(key, idx)
    helpers.bulk(search.os_client(), (
        {"_index": idx, "_id": f"{key}#{i}",
         "_source": {**base, "chunk_id": f"{key}#{i}", "text": piece, "embedding": vector}}
        for i, (piece, vector) in enumerate(zip(pieces, vectors))), refresh=True)
    return f"indexed:{len(pieces)}"


def full_sync(index=None):
    counts = {}
    for key in sources.list_keys():
        status = index_document(key, index)
        counts[status.split(":")[0]] = counts.get(status.split(":")[0], 0) + 1
        print(f"{status:45} {key}")
    print(counts)
    return counts


def indexed_document_ids(index=None):
    res = search.os_client().search(index=index or settings.index_alias, body={
        "size": 0, "query": {"term": {"deletion_status": "active"}},
        "aggs": {"docs": {"terms": {"field": "document_id", "size": 10000}}}})
    return {b["key"] for b in res["aggregations"]["docs"]["buckets"]}


def reconcile(index=None):
    """Backstop for lost delete events: index entries whose source no longer exists."""
    orphans = sorted(indexed_document_ids(index) - set(sources.list_keys()))
    for key in orphans:
        tombstone(key, index)
        print(f"tombstoned orphan {key}")
    print(f"reconciliation: {len(orphans)} orphan(s)")
    return orphans


def validate(index=None):
    """Enforces the data contract: every chunk carries every required field."""
    client, idx = search.os_client(), index or settings.index_alias
    missing = {}
    for field in REQUIRED_FIELDS:
        n = client.count(index=idx, body={"query": {"bool": {"must_not": [{"exists": {"field": field}}]}}})["count"]
        if n:
            missing[field] = n
    if missing:
        raise AssertionError(f"data contract violated, chunks missing fields: {missing}")
    total = client.count(index=idx)["count"]
    print(f"data contract OK: {total} chunks carry all required fields")
    return total


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    {"init": search.ensure_index, "sync": full_sync, "reconcile": reconcile, "validate": validate}[command]()


if __name__ == "__main__":
    main()
