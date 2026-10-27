FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv sync

COPY . .

EXPOSE 8000

# ASGI accepts standards-compliant streamed/chunked OTLP HTTP requests.
CMD ["/opt/venv/bin/uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
