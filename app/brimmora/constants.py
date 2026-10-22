import re

# One message for "nothing relevant" and "relevant but not yours": a different
# message would tell an unauthorized user that restricted documents exist.
NO_EVIDENCE = (
    "I couldn't find enough evidence you have access to in order to answer this. "
    "Try rephrasing, or ask the document owner for access."
)

# Business identifiers the output check verifies against the context
ID_PATTERN = re.compile(r"\b(?:CTR|ENG|INC|SB|LOTO|PROC)-\d+\b")

# The data contract: every indexed chunk must carry these fields
REQUIRED_FIELDS = [
    "document_id", "chunk_id", "source_uri", "source_version", "content_hash",
    "embedding_model", "embedding_version", "last_modified", "indexed_at",
    "region", "tenant_id", "data_classification", "deletion_status", "acl_tags",
]

# Document types whose answers must come from the current source version
TIME_SENSITIVE = {"contract", "procedure"}
