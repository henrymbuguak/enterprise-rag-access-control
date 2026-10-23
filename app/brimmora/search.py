"""The retrieval layer: index mapping, embeddings, hybrid search, reranking."""
from functools import lru_cache

from opensearchpy import OpenSearch

from .config import settings

PIPELINE_ID = "hybrid-pipeline"
# bge models expect this instruction in front of queries (not passages)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
KEYWORD_FIELDS = [
    "document_id", "chunk_id", "source_uri", "source_version", "content_hash", "embedding_model",
    "embedding_version", "chunking", "region", "tenant_id", "data_classification",
    "deletion_status", "acl_tags", "doc_type", "contract_id",
]
# Hybrid scores: min-max normalize BM25 and vector scores, then weight 40/60
PIPELINE = {
    "description": "Normalize and combine BM25 and vector scores",
    "phase_results_processors": [{"normalization-processor": {
        "normalization": {"technique": "min_max"},
        "combination": {"technique": "arithmetic_mean", "parameters": {"weights": [0.4, 0.6]}},
    }}],
}


@lru_cache
def os_client():
    return OpenSearch(hosts=[settings.opensearch_url], timeout=60)


@lru_cache
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


@lru_cache
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.reranker_model)


def embed_passages(texts):
    return embedder().encode(texts, normalize_embeddings=True).tolist()


def embed_query(question):
    return embedder().encode(QUERY_PREFIX + question, normalize_embeddings=True).tolist()


def mapping(dimension):
    props = {f: {"type": "keyword"} for f in KEYWORD_FIELDS}
    props.update({
        "last_modified": {"type": "date"},
        "indexed_at": {"type": "date"},
        "title": {"type": "text"},
        "text": {"type": "text"},
        # Lucene HNSW supports filters applied inside the k-NN search
        "embedding": {"type": "knn_vector", "dimension": dimension,
                      "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"}},
    })
    return {"settings": {"index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}},
            "mappings": {"properties": props}}


def create_index(version):
    """Creates <alias>-<version> sized for the configured embedding model."""
    name = f"{settings.index_alias}-{version}"
    client = os_client()
    if not client.indices.exists(index=name):
        client.indices.create(index=name, body=mapping(embedder().get_embedding_dimension()))
    return name


def ensure_index():
    """Index, alias, and hybrid search pipeline. Safe to run repeatedly."""
    client = os_client()
    name = create_index(settings.embedding_version)
    if not client.indices.exists_alias(name=settings.index_alias):
        client.indices.put_alias(index=name, name=settings.index_alias)
    client.transport.perform_request("PUT", f"/_search/pipeline/{PIPELINE_ID}", body=PIPELINE)
    print(f"index {name} behind alias {settings.index_alias}; pipeline {PIPELINE_ID} ready")
    return name


def security_filters(groups, extra=None):
    """Applied INSIDE the search, so k-NN only ever considers chunks the user may see."""
    return [
        {"term": {"deletion_status": "active"}},
        {"term": {"region": settings.region}},
        {"term": {"tenant_id": settings.tenant_id}},
        {"terms": {"acl_tags": list(groups) or ["__no_groups__"]}},
        *(extra or []),
    ]


def search(question, groups, k=50, mode="hybrid", extra_filters=None, index=None):
    """mode: bm25 | vector | hybrid. Returns up to k chunks (overfetch for later checks)."""
    filters = security_filters(groups, extra_filters)
    bm25 = {"bool": {"must": [{"match": {"text": question}}], "filter": filters}}
    params = {}
    if mode == "bm25":
        query = bm25
    else:
        knn = {"knn": {"embedding": {"vector": embed_query(question), "k": k,
                                     "filter": {"bool": {"filter": filters}}}}}
        if mode == "vector":
            query = knn
        else:
            query = {"hybrid": {"queries": [bm25, knn]}}
            params = {"search_pipeline": PIPELINE_ID}
    body = {"size": k, "_source": {"excludes": ["embedding"]}, "query": query}
    res = os_client().search(index=index or settings.index_alias, body=body, params=params)
    return [dict(hit["_source"], score=hit["_score"]) for hit in res["hits"]["hits"]]


def rerank(question, hits, keep=8):
    """Cross-encoder reorders candidates; returns the best `keep` with rerank_score."""
    if not hits:
        return []
    scores = reranker().predict([(question, h["text"]) for h in hits])
    for hit, score in zip(hits, scores):
        hit["rerank_score"] = float(score)
    return sorted(hits, key=lambda h: h["rerank_score"], reverse=True)[:keep]
