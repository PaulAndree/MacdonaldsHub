# One image for the API and the worker; the start command selects the process.
#   API:    uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000   (default)
#   Worker: python -m app.worker.main
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN useradd --system --create-home --uid 10001 appuser
WORKDIR /srv/backend

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install .

USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
