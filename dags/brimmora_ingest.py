"""Scheduled path: full sync, reconciliation, and the data-contract check, daily."""
import pendulum
from airflow.decorators import dag, task


@dag(schedule="@daily", start_date=pendulum.datetime(2026, 1, 1, tz="UTC"), catchup=False,
     tags=["brimmora"], default_args={"retries": 2})
def brimmora_ingest():
    @task
    def init():
        from brimmora import search
        search.ensure_index()

    @task
    def sync():
        from brimmora import ingest
        return ingest.full_sync()

    @task
    def reconcile():
        from brimmora import ingest
        return ingest.reconcile()

    @task
    def validate():
        from brimmora import ingest
        return ingest.validate()

    init() >> sync() >> reconcile() >> validate()


brimmora_ingest()
