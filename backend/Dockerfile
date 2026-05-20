FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace

ENV PATH="/workspace/.venv/bin:${PATH}" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        openssh-client \
        pandoc \
        rsync \
    && rm -rf /var/lib/apt/lists/*

COPY uv.lock /workspace/uv.lock
COPY backend/pyproject.toml backend/README.md /workspace/backend/
COPY backend/src /workspace/backend/src

WORKDIR /workspace/backend
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "inflab.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
