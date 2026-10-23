"""Event path: MinIO bucket notifications → Redpanda → index updates, deletes, ACL sync."""
import datetime as dt
import json
import logging
from urllib.parse import unquote_plus

from confluent_kafka import Consumer, Producer
from prometheus_client import start_http_server

from . import ingest, search
from .config import settings
from .metrics import DELETE_LAG, EVENT_ERRORS, FRESHNESS, QUARANTINED

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("consumer")


def handle(record):
    name = record["eventName"]
    key = unquote_plus(record["s3"]["object"]["key"])
    happened = dt.datetime.fromisoformat(record["eventTime"].replace("Z", "+00:00"))
    # index_document reads the object's CURRENT state, so replays and out-of-order events are safe
    if name.startswith("s3:ObjectRemoved"):
        ingest.tombstone(key)
        lag = (dt.datetime.now(dt.timezone.utc) - happened).total_seconds()
        DELETE_LAG.observe(lag)
        log.info("deleted %s (%.1fs after the source delete)", key, lag)
    elif name.startswith("s3:ObjectCreated"):
        status = ingest.index_document(key)
        lag = (dt.datetime.now(dt.timezone.utc) - happened).total_seconds()
        FRESHNESS.observe(lag)
        if status.startswith("quarantined"):
            QUARANTINED.labels(status.split(":", 1)[1]).inc()
        log.info("%s %s (%.1fs after the source change)", status, key, lag)


def main():
    start_http_server(8001)
    search.ensure_index()
    search.embedder()
    consumer = Consumer({"bootstrap.servers": settings.kafka_brokers, "group.id": "brimmora-indexer",
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    producer = Producer({"bootstrap.servers": settings.kafka_brokers})
    consumer.subscribe([settings.events_topic])
    log.info("listening on %s", settings.events_topic)
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            log.warning("kafka error: %s", msg.error())
            continue
        try:
            for record in json.loads(msg.value()).get("Records", []):
                handle(record)
        except Exception:
            log.exception("event failed; sending it to the dead-letter topic")
            producer.produce(f"{settings.events_topic}-dlq", msg.value())
            producer.flush()
            EVENT_ERRORS.inc()
        consumer.commit(message=msg, asynchronous=False)   # at-least-once


if __name__ == "__main__":
    main()
