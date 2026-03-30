FROM python:3.12-slim AS base

WORKDIR /app

# System deps for DuckDB spatial/H3 extensions and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy everything, then install
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

# Pre-download DuckDB extensions on build
RUN python -c "\
import duckdb; \
conn = duckdb.connect(':memory:'); \
conn.execute('INSTALL spatial; LOAD spatial;'); \
conn.execute('INSTALL h3 FROM community; LOAD h3;'); \
conn.close(); \
print('DuckDB extensions installed')"

# Run tests as build verification
RUN pytest tests/ -v --tb=short

EXPOSE 8000

# Default: run the API server
CMD ["uvicorn", "parallax.main:app", "--host", "0.0.0.0", "--port", "8000"]
