"""MinIO as the system of record: documents, versions (ETags), and ACL metadata."""
from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from .config import settings

META = "x-amz-meta-"


@lru_cache
def client():
    return Minio(settings.minio_endpoint, access_key=settings.minio_access_key,
                 secret_key=settings.minio_secret_key, secure=False)


def list_keys():
    return sorted(o.object_name for o in client().list_objects(settings.bucket, recursive=True))


def stat(key):
    """Object info, or None when the object no longer exists."""
    try:
        return client().stat_object(settings.bucket, key)
    except S3Error as e:
        if e.code in ("NoSuchKey", "NoSuchObject", "ResourceNotFound"):
            return None
        raise


def metadata(st):
    """User metadata as a plain dict: {'acl-tags': ..., 'classification': ...}."""
    return {k.lower().removeprefix(META): v for k, v in (st.metadata or {}).items()
            if k.lower().startswith(META)}


def _headers(meta):
    return {f"{META}{k}": v for k, v in meta.items() if v}


def put(key, text, meta):
    data = text.encode()
    client().put_object(settings.bucket, key, BytesIO(data), len(data),
                        content_type="text/markdown", metadata=_headers(meta))


def set_metadata(key, updates):
    """Change metadata in place (an ACL change). MinIO emits an ObjectCreated:Copy event."""
    from minio.commonconfig import REPLACE, CopySource
    meta = metadata(stat(key))
    meta.update(updates)
    client().copy_object(settings.bucket, key, CopySource(settings.bucket, key),
                         metadata=_headers(meta), metadata_directive=REPLACE)


def read_text(key):
    resp = client().get_object(settings.bucket, key)
    try:
        data = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    if key.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages)
    if key.endswith(".docx"):
        import docx
        return "\n".join(p.text for p in docx.Document(BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="replace")
