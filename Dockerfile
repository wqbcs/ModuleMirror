FROM --platform=$BUILDPLATFORM python:3.11-slim AS builder

ARG BUILDPLATFORM
ARG TARGETPLATFORM

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi --extras api

FROM python:3.11-slim

ARG TARGETPLATFORM

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY gh_similarity_detector/ gh_similarity_detector/

RUN groupadd -r modulemirror && useradd -r -g modulemirror modulemirror

USER modulemirror

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "gh_similarity_detector.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
