FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# deps first, so a source edit does not re-resolve the environment
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY data/chunks/ ./data/chunks/
COPY data/embeddings/conc3.jsonl ./data/embeddings/
RUN uv sync --frozen --no-dev

# The image is a pinned Handbook snapshot: /app/data is the corpus and is read-only in
# practice. reviews.db must NOT live there — on Container Apps the container filesystem is
# destroyed by scale-to-zero, so /state is a mounted share. Caches are ephemeral by design
# (rebuilding one costs an embedding call); a pending human review is not.
ENV SENTINEL_STATE_DIR=/state
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "sentinel.api:app", "--host", "0.0.0.0", "--port", "8000"]
