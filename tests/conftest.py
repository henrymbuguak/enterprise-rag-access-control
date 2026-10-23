import httpx
import psycopg
import pytest

from brimmora.config import settings


def pytest_configure(config):
    config.addinivalue_line("markers", "db: needs the Postgres service")
    config.addinivalue_line("markers", "integration: needs OpenSearch and the models")


@pytest.fixture
def db():
    try:
        psycopg.connect(settings.pg_app_dsn, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")


@pytest.fixture
def opensearch():
    try:
        httpx.get(settings.opensearch_url, timeout=3)
    except httpx.HTTPError:
        pytest.skip("OpenSearch not reachable")
