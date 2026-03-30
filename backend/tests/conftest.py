import duckdb
import pytest


@pytest.fixture
def db():
    """In-memory DuckDB with extensions for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    yield conn
    conn.close()
