FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt requirements.txt
COPY distributed/requirements.txt distributed-requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r distributed-requirements.txt && \
    addgroup --system omnisignal && \
    adduser --system --ingroup omnisignal --home /nonexistent --no-create-home omnisignal

COPY --chown=omnisignal:omnisignal distributed ./distributed

USER omnisignal

EXPOSE 8000
EXPOSE 9000

ENTRYPOINT ["python", "-m", "distributed.scripts.entrypoint"]
