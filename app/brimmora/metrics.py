"""Every Prometheus metric the platform exposes, defined in one place."""
from prometheus_client import Counter, Histogram

LAG_BUCKETS = (1, 5, 15, 30, 60, 120, 300, 600, 1800)

# Request path (api)
REQUESTS = Counter("brimmora_requests_total", "Answered requests", ["route", "outcome"])
ROUTES = Counter("brimmora_route_total", "Router decisions", ["route"])
LATENCY = Histogram("brimmora_request_seconds", "End-to-end request latency",
                    buckets=(0.5, 1, 2, 4, 8, 16, 32, 64, 128))
GATE_FAILURES = Counter("brimmora_quality_gate_failures_total", "Retrieval quality gate failures", ["gate"])
EMPTY_CONTEXT = Counter("brimmora_empty_context_total", "Requests with no relevant authorized context", ["group"])
OUTPUT_CHECK = Counter("brimmora_output_check_failures_total", "Answers blocked by the output check")
LLM_TOKENS = Counter("brimmora_llm_tokens_total", "LLM tokens used", ["purpose", "kind"])
CACHE = Counter("brimmora_answer_cache_total", "Answer cache lookups", ["result"])

# Event path (consumer)
DELETE_LAG = Histogram("brimmora_delete_propagation_seconds", "Source delete to unsearchable", buckets=LAG_BUCKETS)
FRESHNESS = Histogram("brimmora_index_freshness_seconds", "Source change to searchable", buckets=LAG_BUCKETS)
QUARANTINED = Counter("brimmora_quarantined_events_total", "Documents quarantined by the event path", ["reason"])
EVENT_ERRORS = Counter("brimmora_event_errors_total", "Events sent to the dead-letter topic")
