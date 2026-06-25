FROM rust:1.95-slim AS rust-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY src/_module_mirror_rust/ .

RUN mkdir -p src_backup && cp -r src src_backup/ \
    && echo 'fn main() {}' > src/lib.rs \
    && cargo build --release \
    && rm -rf src \
    && cp -r src_backup/src src \
    && rm -rf src_backup

RUN touch src/lib.rs && cargo build --release

FROM python:3.12-slim AS py-builder

WORKDIR /app

RUN pip install --no-cache-dir maturin

COPY pyproject.toml ./
COPY src/_module_mirror_rust/ src/_module_mirror_rust/
COPY gh_similarity_detector/ gh_similarity_detector/

COPY --from=rust-builder /build/target/release/lib_module_mirror_rust.so src/_module_mirror_rust/

RUN maturin develop --release --manifest-path src/_module_mirror_rust/Cargo.toml || true \
    && pip install --no-cache-dir ".[api]"

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd -r modulemirror && useradd -r -g modulemirror modulemirror

COPY --from=py-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=py-builder /usr/local/bin /usr/local/bin
COPY --from=py-builder /app/gh_similarity_detector/ gh_similarity_detector/

USER modulemirror

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "gh_similarity_detector.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
