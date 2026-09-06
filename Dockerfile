FROM python:3.12-slim AS build

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 lumina

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=lumina:lumina *.py ./
COPY --chown=lumina:lumina frontend/ ./frontend/

# The SQLite database and the ChromaDB store are written at runtime; keep them
# in a volume so a restart does not lose sessions or re-seed the vector store.
RUN mkdir -p /app/data && chown lumina:lumina /app/data
VOLUME ["/app/data"]

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/tutor.db \
    CHROMA_PATH=/app/data/chroma_db \
    BIND_HOST=0.0.0.0 \
    PORT=8000

USER lumina
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["sh", "-c", "uvicorn main:app --host ${BIND_HOST} --port ${PORT}"]
